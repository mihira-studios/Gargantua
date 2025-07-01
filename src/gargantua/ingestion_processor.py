import os
import sys
import re
import logging
import datetime
import shutil
import pandas as pd
from enum import Enum, unique
import subprocess
import concurrent.futures
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
)


from .ingestion_operations import ProxyGenerationOperation, CopyFileOperation, MovGenerationOperation
from .csv_file_reader import MVLCSVReader
from .ingestion_utils import check_missing_frames
from .ingestion_builder import SequenceBuilder
from .ingestion_utils import get_files_and_sequences

@unique
class INGESTIONPROCESS(Enum):
    INGEST = 1
    EGRESS = 2
	
class MVLIngestionProcessor():

	def __init__(self, args):
		self.data = vars(args)
		if self.data.get('process'):
			self.process_to_mvl()
		elif not self.data.get('process'):
			self.process_from_mvl()
		
		self.copy_op = CopyFileOperation()
		self.proxy_op = ProxyGenerationOperation()
		self.mov_op = MovGenerationOperation()
    
	def process_to_mvl(self):
		logging.info(f"process to mvl started ...")
		source_dir = self.data.get("source")
		if not source_dir and not os.path.isdir(source_dir):
			source_dir = "C:" 
		
		project_path = os.path.join(source_dir, self.data.get("project"))
		logging.info(f"project path : {project_path}")
		if not os.path.isdir(project_path):
			logging.error(f"Project path not found: {project_path}")
			exit(1)
		else:
			logging.info(f"Using project path: {project_path}")
			source_dir = project_path

		#add vault and IO process path
		vault_path = os.path.join(source_dir, "vault")
		input_date = str(self.data.get("input_date"))
		if input_date and len(input_date) == 8:
			try:
				date_obj = datetime.datetime.strptime(input_date,  "%Y%m%d")
				date_str = date_obj.strftime("%Y%m%d")
				self.proces_vendor(date_str, vault_path, INGESTIONPROCESS.INGEST)
			except ValueError:
				logging.error(f"Error: Invalid date  {input_date} format for vault path. Use YYYYMMDD.")
				sys.exit(1)
			except Exception as e:
				logging.error(f"Error: An unexpected error occured {e}")
				sys.exit(1)
		
	def proces_vendor(self, date_str, vault_path, process):
		
		if process == INGESTIONPROCESS.INGEST:
			vault_path = os.path.join(vault_path, "to_mvl")
		elif process == INGESTIONPROCESS.EGRESS:
			vault_path = os.path.join(vault_path, "from_mvl")

		logging.info(f"vault path {vault_path}")

		vendor = self.data.get("vendor") 
		if vendor:
			vendor_date_path = os.path.join(vault_path, vendor, date_str)
			if os.path.isdir(vendor_date_path):
				logging.info(f"Using path: {vault_path}")
				self.data["source"] = vendor_date_path
			else:
				logging.error(f"Vendor path not found: {vault_path}")
				exit(1)
		else:
			# No vendor provided, check all directories under vault
			vault_vendors = vault_path
			if os.path.isdir(vault_vendors):
				self.data["source"] = [] # make source_dir a list.
				found_date_path = False
				for vendor_dir in os.listdir(vault_vendors):
					vendor_date_path = os.path.join(vault_vendors, vendor_dir, date_str)
					if os.path.isdir(vendor_date_path):
						logging.info(f"Using vault path: {vendor_date_path}")
						self.data["source"].append(vendor_date_path) #add to list.
						found_date_path = True
				if not found_date_path:
					logging.error(f"Vault path with date {date_str} not found under any vendor.")
					exit(1)
			else:
				logging.error(f"Vault vendors directory not found: {vault_vendors}")
				exit(1)

	def validate_destination(self):
		destination_dir = self.data.get("destination")
		if not destination_dir:
			logging.error("Destination directory not provided.")
			exit(1)

		if not os.path.isdir(destination_dir):
			dest = self.data.get("destination")
			logging.info(f"Error: {dest} is not a valid directory.")
			return

		if not self.data.get("project"):
			logging.info(f"Error: {self.data.get('project')} is not a valid project.")
			return 
    
	def process_from_mvl(self):
		return NotImplementedError("Not implement yet!")
	
	def execute(self):
		"""
		Processes folders, gets all files and file sequences from resolution folders.

		Args:
		base_path (str): The base path containing the folders to process.
		"""
		paths = [self.data.get("source")]
		if not isinstance(paths, list):
			return 
		
		file_tasks = []
		sequence_tasks = []
		
		for base_path in paths:
			if not os.path.exists(base_path):
				logging.error(f"Error: Path '{base_path}' does not exist.")
				return
			try:
				current_scene = None
				current_shot = None
				for root, dirs, _ in os.walk(base_path):
					for folder_name in dirs:
						# Find scene_shot folders (e.g., 48_14)
						sc_match = re.match(r"^SC_(\d+)", folder_name)
						if sc_match:
							scene = sc_match.group(1)
							current_scene = scene
							status = self.readCSV(os.path.join(root, f"SC_{current_scene}"))
						
						scene_shot_match = re.match(rf"{current_scene}_([A-Za-z0-9_\-]+)", folder_name)
						if status and scene_shot_match:
							current_shot = scene_shot_match.group(1)
							scene_shot_path = os.path.join(root, folder_name)
                            # Find resolution folders (e.g., 4448x3086) inside scene_shot folders
							for sub_dir_name in os.listdir(scene_shot_path):
								sub_dir_path = os.path.join(scene_shot_path, sub_dir_name)
								if os.path.isdir(sub_dir_path): 
									resolution_match = re.match(r"\d+x\d+", sub_dir_name)
									if resolution_match:
										resolution = resolution_match.group(0)
										files, sequences = get_files_and_sequences(sub_dir_path,current_scene, current_shot, resolution)
										if files:
											file_tasks.append(files)
										if sequences:

											sequence_tasks.append(sequences)
			except Exception as e:
				logging.error(f"An error occurred: {e}")
			
		
		# Run file and sequence copy tasks in parallel
		with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
			# File copy tasks
			all_files = [file_path for files_list in file_tasks for file_path in files_list]
			file_futures = [executor.submit(self.copy_file, file_path) for file_path in all_files]
			all_sequences = [seq for seq_list in sequence_tasks for seq in seq_list]
			# Sequence copy tasks
			sequence_futures = [
				executor.submit(
					SequenceBuilder(
						sequence=seq,
						copy_op=self.copy_op,
						proxy_op=self.proxy_op,
						mov_op=self.mov_op
					).build, False, self.data
				) for seq in all_sequences
			]
			# Wait for all to finish
			for future in concurrent.futures.as_completed(file_futures + sequence_futures):
				future.result()

	def readCSV(self, path):
		from os import listdir
		files= [f for f in listdir(path) if f.endswith(".csv")]
		
		if len(files):
			reader_no_header = MVLCSVReader(os.path.join(path,files[0]))
			reader_no_header.read_csv(skip_header=False)
			# Create mapping where the first column is the key (no header)
			mapping = reader_no_header.create_dictionary_mapping(skip_header=False)
			for key, values in mapping.items():
				self.data[key] = values
		else:
			logging.info(f"No csv file found at {path}!")
			return False
		
		return True
        
	def parse_filename(self, filename):
		"""Parses the filename and returns the extracted information."""
		pattern = r"^(i|O)_([A-Za-z0-9]+)_(\d+-\d+)(?:_([A-Za-z0-9]+))?_v(\d+)$"
		match = re.match(pattern, filename)

		if match:
			io, project, scene_shot, optional, version = match.groups()
			return {
				"io": io,
				"project": project,
				"scene_shot": scene_shot,
				"optional": optional,
				"version": version,
			}
		else:
			return None

	def copy_file(self, file_path):
		"""
			Copies a single file to the output path.
			Args:
				file_path(str) : path of the file to copy
		"""
		try:
			base_name, extension = os.path.splitext(os.path.basename(file_path))
			output_path = generate_output_paths(1001, extension.lower(), self.data)  # 1001 for single files
			plate_path = output_path['plate']
			if output_path:
				os.makedirs(os.path.dirname(plate_path), exist_ok=True)
				shutil.copy2(file_path, plate_path)
				logging.info(f"Copied file: {os.path.basename(file_path)} to {plate_path}")
		except Exception as e:
			error_msg = f"Error copying file {os.path.basename(file_path)}: {e}"
			return False

	def copy_sequences(self, sequences):
		"""
			Copies the selected files and sequences to the created folder structure.
			Args:
				files(list) : list of files paths
				sequences(list) : list all the sequence found in paths
		"""
		if sequences:
			for seq in sequences:
				builder = SequenceBuilder(
					sequence=seq,
					copy_op=self.copy_op,
					proxy_op=self.proxy_op,
					mov_op=self.mov_op
				)
				builder.build(False, self.data)

		return True
	
	def display_results(self, files, sequences):
		"""Displays the identified files and sequences."""
		logging.info("Identified Files:")
		if files:
			for file_path in files:
				logging.info(f"  - {file_path}")
			else:
				logging.info("  No individual files found.")

			logging.info("\nIdentified File Sequences:")
			if sequences:
				for seq in sequences:
					logging.info(f"  - Base Name: {seq['base_name']}.{'#' * seq['padding']}.{seq['extension']}")
					logging.info(f"    Frame Range: {seq['start']} - {seq['end']}")
					logging.info(f"    Total Frames: {seq['end'] - seq['start'] + 1}")
				else:
					logging.info("  No file sequences found.")

	def create_mov_from_exrs(input_pattern, output_mov, fps=24):
		"""
		Create a .mov file from an image sequence using ffmpeg.

		Args:
			input_pattern (str): Input image sequence pattern, e.g. 'path/to/image.%04d.exr'
			output_mov (str): Output .mov file path.
			fps (int): Frames per second.
		"""
		logging.info(f"Running: ffmpeg -y -framerate {fps} -i {input_pattern} -c:v prores_ks -pix_fmt yuv422p10le {output_mov}")
		import ffmpeg
        
		(
			ffmpeg.input(input_pattern, framerate=fps)
			.output(output_mov, vcodec='prores_ks', pix_fmt='yuv422p10le')
			.overwrite_output()
			.run()
		)
    
	def generate_proxy_from_exr_using_convert(input_path, output_path, format):
		"""
		Generates an image file (JPEG or PNG) from an EXR file using OpenIMAJIO.

		Args:
			input_path (str): Path to the input EXR file.
			output_path (str): Path to save the generated image file.
			format (str): The desired output image format (jpeg or png).
		"""
		format = format.lower()
		if format not in ["jpeg", "png"]:
			logging.info(f"Error: Unsupported output image format: {format}. Please use 'jpeg' or 'png'.")
			return

		try:
			# Construct the OpenImageIO command for EXR to image conversion
			command = [
				"openimageio",
				"convert",
				input_path,
				"-o",
				output_path,
				"-format",
				format,
				# Add other OpenImageIO options as needed, e.g., exposure, tone mapping
				# Example for setting exposure:
				# "-e", "0.5",
				# Example for using a specific tone mapping operator:
				# "-tonemap", "aces",
			]

			logging.info(f"Running OpenImageIO command: {' '.join(command)}")
			subprocess.run(command, check=True, capture_output=True)
			logging.info(f"Successfully generated image: {output_path}")

		except FileNotFoundError:
			logging.info("Error: OpenImageIO command not found. Make sure it's in your system's PATH.")
		except subprocess.CalledProcessError as e:
			logging.info(f"Error generating image with OpenImageIO:")
			logging.info(f"Command: {' '.join(e.cmd)}")
			logging.info(f"Return Code: {e.returncode}")
			logging.info(f"Stdout: {e.stdout.decode()}")
			logging.info(f"Stderr: {e.stderr.decode()}")
		except Exception as e:
			logging.info(f"An unexpected error occurred: {e}")

	def exr_to_ffmpeg_pattern(self, outpath):
		"""
			Converts an EXR file path to an ffmpeg sequence pattern.
			Example: ..._1001_f4448x3096.exr -> ..._%04d_f4448x3096.exr
			Returns None if no frame number pattern is found.
		"""
		dir_name, file_name = os.path.split(outpath)
		# Try to match a frame number pattern
		match = re.search(r'_(\d{4})_', file_name) and not re.search(r'_(\d{4})(?=\.exr$)', file_name)
		logging.info (f"match : {match}")
		if not match:
			return None
		# Replace the frame number (e.g., 1001) with %04d
		pattern = re.sub(r'_(\d{4})_', r'_%04d_', file_name)
		# If frame number is at the end before .exr, handle that too
		pattern = re.sub(r'_(\d{4})(?=\.exr$)', r'_%04d', pattern)
		return os.path.join(dir_name, pattern)