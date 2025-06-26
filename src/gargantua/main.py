import os
import sys
import argparse
import re
import weakref
import threading
import functools
import collections
import enum
import math
#import imath
import warnings
import logging
import datetime
import shutil
import io
import pandas as pd
import csv
from enum import Enum, unique
import subprocess

@unique
class INGESTIONPROCESS(Enum):
    INGEST = 1
    EGRESS = 2


try:
    import Gaffer
    is_gaffer_environment = True
except ImportError:
    is_gaffer_environment = False


class CSVReader:
	"""
	A class to read CSV files and create a dictionary where the first column
	is the key and the remaining columns are the values (as a list).
	"""
	def __init__(self, file_path):
		"""
		Initializes the CSVReader with the path to the CSV file.
		Args:
			file_path (str): The path to the CSV file.
		"""
		self.file_path = file_path
		self.data = []
		self.header = None

	def read_csv(self, delimiter=',', quotechar='"', skip_header=False):
		"""
		Reads the CSV file.

		Args:
			delimiter (str, optional): The character used to separate fields. Defaults to ','.
			quotechar (str, optional): The character used to quote fields containing special characters. Defaults to '"'.
			skip_header (bool, optional): Whether to skip the first row as the header. Defaults to False.

		Returns:
			list: A list of lists, where each inner list represents a row in the CSV file.
					Returns an empty list if the file cannot be read.
		"""
		self.data = []
		self.header = None
		try:
			with open(self.file_path, 'r', newline='', encoding='utf-8') as csvfile:
				reader = csv.reader(csvfile, delimiter=delimiter, quotechar=quotechar)
				for i, row in enumerate(reader):
					if skip_header and i == 0:
						self.header = row
					else:
						self.data.append(row)
			return self.data
		except FileNotFoundError:
			print(f"Error: File not found at '{self.file_path}'")
			return []
		except Exception as e:
			print(f"Error reading CSV file: {e}")
			return []

	def get_data(self):
		"""
		Returns the data read from the CSV file.

		Returns:
			list: A list of lists representing the rows.
		"""
		return self.data

	def get_header(self):
		"""
		Returns the header row, if `skip_header` was set to True during reading.

		Returns:
			list or None: The header row as a list, or None if no header was skipped.
		"""
		return self.header

	def create_dictionary_mapping(self, key_column_index=0, skip_header=True):
		"""
		Creates a dictionary where the value in the specified key column
		is the key, and the remaining columns in the row are the value (as a list).

		Args:
			key_column_index (int, optional): The index of the column to use as the key (0-based). Defaults to 0 (the first column).
			skip_header (bool, optional): Whether the CSV file has a header row. Defaults to True.

		Returns:
			dict: A dictionary where the key is from the specified column and the
					value is a list of the remaining column values in that row.
					Returns an empty dictionary if no data is read or the key column
					index is invalid.
		"""
		mapping = {}
		if not self.data:
			print("Warning: No data has been read from the CSV file.")
			return mapping

		if key_column_index < 0 or (self.data and key_column_index >= len(self.data[0])):
			print(f"Error: Key column index {key_column_index} is out of bounds.")
			return mapping

		start_row = 1 if skip_header and self.header else 0
		for i in range(start_row, len(self.data)):
			row = self.data[i]
			if row:  # Ensure the row is not empty
				key = row[key_column_index].strip()
				values = [item.strip() for j, item in enumerate(row) if j != key_column_index]
				mapping[key] = values

		return mapping

	def create_dictionary_mapping_by_name(self, key_column_name, skip_header=True):
		"""
		Creates a dictionary where the value in the specified key column name
		is the key, and the remaining columns in the row are the value (as a list).
		Requires the CSV to have a header and skip_header to be True during reading.

		Args:
			key_column_name (str): The name of the column to use as the key.
			skip_header (bool, optional): Whether the CSV file has a header row. Defaults to True.

		Returns:
			dict: A dictionary where the key is from the specified column and the
					value is a list of the remaining column values in that row.
					Returns an empty dictionary if no data is read, the header
					was not read, or the key column name is not found.
		"""
		mapping = {}
		if not self.data:
			print("Warning: No data has been read from the CSV file.")
			return mapping

		if not self.header and skip_header:
			print("Error: Header not read. Call read_csv() with skip_header=True first.")
			return mapping

		try:
			key_column_index = self.header.index(key_column_name)
			mapping = self.create_dictionary_mapping(key_column_index=key_column_index, skip_header=True)
		except ValueError:
			print(f"Error: Key column '{key_column_name}' not found in the header.")
		return mapping
	
class VFXFileProcessor():

	def __init__(self, args):
		self.args = args
		
		if is_gaffer_environment:
			self.data = {
				"source": args["source"].value,
				"destination": args["destination"].value,
				"project": args["project"].value,
				"input_date": args["input_date"].value,
				"data_type": args["data_type"].value,
				"process": args["process"].value,
				"vendor": args["vendor"].value,
				"hires": args["hires"].value,
				"camera": args["camera"].value,
				"take": args["take"].value,
				"resolution": args["resolution"].value,
				"force": args["force"].value,
				"proxy": args["proxy"].value,
				"extensions": []
			}

			if self.args["proxy"].value:
				self.data["extensions"].append("jpg")
			if self.args["mov"].value:
				self.data["extensions"].append("mov")
			if self.args["hires"].value:
				self.data["extensions"].append("hires")
			if not self.data.get("data_type"):
				self.data["data_type"] = "exr"

			self.process = self.args["process"].value
		
		else:

			self.data = {
				"source": args.source,
				"destination": args.destination,
				"project": args.project,
				"input_date": args.input_date,
				"data_type": args.data_type,
				"process": args.process,
				"vendor": args.vendor,
				"hires": args.hires,
				"camera": args.camera,
				"take": args.take,
				"resolution": args.resolution,
				"force": args.force,
				"proxy": args.proxy,
				"proxy": []
			}

			if self.args.proxy:
				self.data["proxy"].append("jpg")
			if self.args.mov:
				self.data["proxy"].append("mov")
			if not self.data.get("data_type"):
				self.data["data_type"] = "exr"
			
			self.process = self.args.process

		cwd =  os.getcwd()
		reader_no_header = CSVReader( os.path.join(cwd,"data", "shot_folders_to_be_renamed.csv"))
		reader_no_header.read_csv(skip_header=False)

		# Create mapping where the first column is the key (no header)
		first_column_mapping_no_header = reader_no_header.create_dictionary_mapping(skip_header=False)
		print("\nDictionary Mapping (First Column as Key, No Header):")
		for key, values in first_column_mapping_no_header.items():
			self.data[key] = values
			print(f"{key}: {self.data[key]}")
		
		if self.process:
			self.process_to_mvl()
		elif not self.proces:
			self.process_from_mvl()

	def process_to_mvl(self):
		print(f"process to mvl started ...")
		source_dir = self.data.get("source")
		if not source_dir and not os.path.isdir(source_dir):
			source_dir = "C:" 

		#process the project path
		
		project_path = os.path.join(source_dir, self.data.get("project"))
		print(f"project path : {project_path}")
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

		print(f"vault path {vault_path}")

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
			print(f"Error: {dest} is not a valid directory.")
			return

		if not self.data.get("project"):
			print(f"Error: {self.data.get('project')} is not a valid project.")
			return 
    
	def process_from_mvl(self):
		pass
	
	def execute(self):
		"""
		Processes folders, gets all files and file sequences from resolution folders.

		Args:
		base_path (str): The base path containing the folders to process.
		"""
		paths = self.data.get("source")
		if not isinstance(paths, list):
			paths = [paths]
		
		for base_path in paths:
			if not os.path.exists(base_path):
				logging.error(f"Error: Path '{base_path}' does not exist.")
				return
			
			try:
				for root, dirs, _ in os.walk(base_path):
					for folder_name in dirs:
						# Find scene_shot folders (e.g., 48_14)
						sc_match = re.match(r"^SC_(\d+)", folder_name)
						if sc_match:
							self.data["scene"] = sc_match.group(1)
						
						scene_shot_match = re.match(rf"{self.data.get('scene')}_(\d+)", folder_name)

						if scene_shot_match:
							self.data["shot"] = scene_shot_match.group(1)
							scene_shot_path = os.path.join(root, folder_name)
							
							# Find resolution folders (e.g., 4448x3086) inside scene_shot folders
							for sub_dir_name in os.listdir(scene_shot_path):
								sub_dir_path = os.path.join(scene_shot_path, sub_dir_name)
								if os.path.isdir(sub_dir_path): 
									resolution_match = re.match(r"\d+x\d+", sub_dir_name)
									if resolution_match:
										self.data["resolution"] = resolution_match.group(0)
										files, sequences = self.get_files_and_sequences(sub_dir_path)
										self.copy_files_to_structure(files, sequences, self.data.get("destination"))
									else:
										logging.error(f"No valid resolution folders found in the path:  {sub_dir_path}")
				
			except Exception as e:
				logging.error(f"An error occurred: {e}")

	def get_files_and_sequences(self, root_dirs):
		"""
		Reads a directory and identifies individual files and file sequences.
		Returns:
			tuple: A tuple containing two lists:
				- files (list): A list of individual file paths.
				- sequences (list): A list of dictionaries representing file sequences.
		"""
		files = []
		sequences = []
		processed_files = set()
		#sequence_regex = re.compile(r"^(.*)\_(\d+)\_([a-zA-Z0-9]+)$")
		sequence_regex = re.compile(r"^(.+?)_(\d+)\.([a-zA-Z0-9]+)$")
			
		#root_dirs  = self.data.get("source")
		print (f"paths to process: {root_dirs}")
		if not isinstance(root_dirs, list):
			root_dirs = [root_dirs]
		
		for root_dir in root_dirs:
			all_items = sorted([os.path.join(root_dir, item) for item in os.listdir(root_dir)])
			for item_path in all_items:
				if os.path.isfile(item_path) and item_path not in processed_files:
					match = sequence_regex.match(os.path.basename(item_path))
					if match:
						print (f"{match.groups()}")
						base_name, frame_number_str, extension = match.groups()
						padding = len(frame_number_str)
						frame_number = int(frame_number_str)

						sequence_files = []
						start_frame = frame_number
						end_frame = frame_number

						for seq_file_path in all_items:
							if os.path.isfile(seq_file_path) and seq_file_path not in processed_files:
								seq_match = sequence_regex.match(os.path.basename(seq_file_path))
								
								if seq_match and seq_match.group(1) == base_name and seq_match.group(3) == extension and len(seq_match.group(2)) == padding:
									seq_frame_number = int(seq_match.group(2))
									sequence_files.append(seq_file_path)
									processed_files.add(seq_file_path)
									start_frame = min(start_frame, seq_frame_number)
									end_frame = max(end_frame, seq_frame_number)

						if len(sequence_files) > 1:
							sequences.append({
								'base_name': base_name,
								'padding': padding,
								'start': start_frame,
								'end': end_frame,
								'extension': extension,
								'paths': sequence_files
							})
						else:
							files.append(item_path)
					else:
						files.append(item_path)

		return files, sequences

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

	def generate_output_path(self, base_name, frame_number, extension):
		"""Generates the output file path based on the specified naming convention."""
		#parsed_info = self.parse_filename(base_name
		for key in self.data.keys():
			if self.data.get("scene") in key or self.data.get("shot") in key:
				shot = self.data[key][0].split('_')[-1]
				break

		
		frame_str = str(frame_number).zfill(4)  # Pad frame number with leading zeros
		output_filename = self.generate_new_filename(frame_str, extension)

		destination = self.data.get("destination")
		project = self.data.get("project", "gen63")
		sc = self.data.get("scene")
		camera = self.data.get("camera", "camA")
		take = self.data.get("camera", "camA")

		#print(f"destination {destination}, project {project}, sc {sc} camera {camera}")

		if not destination:
			logging.error("destination key error")
			exit(1)
		if not project:
			logging.error("project key error")
			exit(1)
		if not sc:
			logging.error("scene key error")
			exit(1)
		if not camera:
			camera ="camA"
		if not take:
			take = "takeA"

		output_path = os.path.join(destination, project, f"SC_{sc}", f"SH_{shot}", "plates", camera, take)
		if self.data.get("take"):
			output_path = os.path.join(output_path, self.data.get("take"))
		output_path = os.path.join(output_path, output_filename)
		return output_path
	
	def generate_new_filename(self, frame, ext):
		"""
		Generates a new filename based on the provided file information.

		Args:
			file_info (dict): A dictionary containing file information.

		Returns:
			str: The new filename.
		"""

		filename_placeholder = "{sceneshot}_{type}_{camera}_{take}_{frame_number}_f{resolution}{ext}"
 
		for key in self.data.keys():
			if self.data.get("scene") in key or self.data.get("shot") in key:
				csv_data = self.data[key]
				break

		file_data = {
			#"job": self.data.get('project', "gen63"),
			"sceneshot": csv_data[0],
			"type":csv_data[1],
			"camera" :self.data.get("camera") if self.data.get("camera") is not "" else "camA",
			"take": self.data.get("take")if self.data.get("take") is not "" else "takeA",
			"frame_number": frame,
			"resolution": self.data['resolution'],
			"ext": ext,
		}

		filename = filename_placeholder.format(**file_data)
		return filename

	def check_missing_frames(self, sequences):
		"""Checks for missing frames in the given files and sequences, without copying."""

		error_msg = None

		# Check for missing frames in sequences
		for seq in sequences:
			sorted_paths = sorted(seq['paths'], key=lambda path: int(os.path.splitext(os.path.basename(path))[0].split('_')[-1]))
			frame_numbers = []

		for path in sorted_paths:
			try:
				frame_number = int(os.path.splitext(os.path.basename(path))[0].split('_')[-1])
				frame_numbers.append(frame_number)
			except Exception as e:
				error_msg = f"Error extracting frame number from {os.path.basename(path)}: {e}"
				logging.error(error_msg)

		if frame_numbers:
			expected_frames = list(range(min(frame_numbers), max(frame_numbers) + 1))
			missing_frames = [f for f in expected_frames if f not in frame_numbers]

			if missing_frames:
				error_msg = f"Missing sequence frames for {seq['paths'][0]}: {missing_frames}, use -force with the executable if you need to ingets these files"
				logging.error(error_msg)

		if error_msg:
			logging.error(error_msg)
			return True

		return False

	def copy_files_to_structure(self, files, sequences, destination_asset_dir):
		"""Copies the selected files and sequences to the created folder structure."""
		publish_dirs = destination_asset_dir

		error_msg = None

		m_status = self.check_missing_frames(sequences)

		print(f"missing frames: {m_status}")
		if m_status and self.data.get("force") == False:
			return
		elif not m_status or self.data.get("force") == True:
			for file_path in files:
				try:
					base_name, extension = os.path.splitext(os.path.basename(file_path))
					output_path = self.generate_output_path(base_name, 1001, extension.lower())  # 1001 for single files
					if output_path:
						os.makedirs(os.path.dirname(output_path), exist_ok=True)
						shutil.copy2(file_path, output_path)
						print(f"Copied file: {os.path.basename(file_path)} to {output_path}")
				except Exception as e:
					error_msg = f"Error copying file {os.path.basename(file_path)}: {e}"

			if sequences is not None:
				for seq in sequences:
					# Sort paths based on the last number after splitting by '_'
					sorted_paths = sorted(seq['paths'], key=lambda path: int(os.path.splitext(os.path.basename(path))[0].split('_')[-1]))
					frame_counter = 1001
					for path in sorted_paths:
						if path is None:
							logging.error("Warning: Encountered a None path in the sequence.")
							continue  # Skip to the next iteration
						try:
							base_name, extension = os.path.splitext(os.path.basename(path))
							output_path = self.generate_output_path(base_name, frame_counter, extension)
							if output_path:
								os.makedirs(os.path.dirname(output_path), exist_ok=True)
								shutil.copy2(path, output_path)
								print(f"Copied sequence file: {os.path.basename(path)} to {output_path}")
								frame_counter += 1
						except Exception as e:
							error_msg = f"Error copying sequence file {os.path.basename(path)}: {e}"

			if error_msg:
				print(f" {error_msg}")
				return False

		return True

	def display_results(self, files, sequences):
		"""Displays the identified files and sequences."""
		print("Identified Files:")
		if files:
			for file_path in files:
				print(f"  - {file_path}")
			else:
				print("  No individual files found.")

			print("\nIdentified File Sequences:")
			if sequences:
				for seq in sequences:
					print(f"  - Base Name: {seq['base_name']}.{'#' * seq['padding']}.{seq['extension']}")
					print(f"    Frame Range: {seq['start']} - {seq['end']}")
					print(f"    Total Frames: {seq['end'] - seq['start'] + 1}")
				else:
					print("  No file sequences found.")

	def create_jpeg_from_exr(exr_path, jpeg_path, display_window=None, data_window=None, channels=None):
		"""
		Creates a JPEG image from an EXR image using Gaffer.

		Args:
			exr_path (str): The path to the EXR image.
			jpeg_path (str): The path to save the JPEG image.
			display_window (IECore.Box2i, optional): The display window to use.
			data_window (IECore.Box2i, optional): The data window to use.
			channels (list of str, optional): The channels to include in the JPEG.
		"""

		script = Gaffer.ScriptNode()

		# Read the EXR image
		reader = GafferImage.ImageReader()
		script["exrReader"] = reader
		reader["fileName"].setValue(exr_path)

		# Convert to JPEG
		writer = GafferImage.ImageWriter()
		script["jpegWriter"] = writer
		writer["fileName"].setValue(jpeg_path)
		writer["in"].setInput(reader["out"])
		writer["fileFormat"].setValue("JPEG")

		# Apply display window, data window, and channels if provided
		if display_window:
			writer["displayWindow"].setValue(display_window)
		if data_window:
			writer["dataWindow"].setValue(data_window)
		if channels:
			writer["channels"].setValue(IECore.StringVectorData(channels))

		# Execute the writer node
		writer["task"].execute()

		print(f"JPEG created: {jpeg_path}")

	def create_mov_from_exrs(exr_sequence_path, mov_path, fps=24, display_window=None, data_window=None, channels=None):
		"""
		Creates a MOV video from a sequence of EXR images using Gaffer.

		Args:
			exr_sequence_path (str): The path to the EXR sequence (e.g., /path/to/image.%04d.exr).
			mov_path (str): The path to save the MOV video.
			fps (int, optional): Frames per second for the MOV video. Defaults to 24.
			display_window (IECore.Box2i, optional): The display window to use.
			data_window (IECore.Box2i, optional): The data window to use.
			channels (list of str, optional): The channels to include in the MOV.
		"""

		script = Gaffer.ScriptNode()

		# Read the EXR sequence
		reader = GafferImage.ImageReader()
		script["exrReader"] = reader
		reader["fileName"].setValue(exr_sequence_path)

		# Write the MOV video
		writer = GafferImage.ImageWriter()
		script["movWriter"] = writer
		writer["fileName"].setValue(mov_path)
		writer["in"].setInput(reader["out"])
		writer["fileFormat"].setValue("MOV")
		writer["fps"].setValue(fps)

		# Apply display window, data window, and channels if provided
		if display_window:
			writer["displayWindow"].setValue(display_window)
		if data_window:
			writer["dataWindow"].setValue(data_window)
		if channels:
			writer["channels"].setValue(IECore.StringVectorData(channels))

		# Execute the writer node
		writer["task"].execute()

		print(f"MOV created: {mov_path}")

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
			print(f"Error: Unsupported output image format: {format}. Please use 'jpeg' or 'png'.")
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

			print(f"Running OpenImageIO command: {' '.join(command)}")
			subprocess.run(command, check=True, capture_output=True)
			print(f"Successfully generated image: {output_path}")

		except FileNotFoundError:
			print("Error: OpenImageIO command not found. Make sure it's in your system's PATH.")
		except subprocess.CalledProcessError as e:
			print(f"Error generating image with OpenImageIO:")
			print(f"Command: {' '.join(e.cmd)}")
			print(f"Return Code: {e.returncode}")
			print(f"Stdout: {e.stdout.decode()}")
			print(f"Stderr: {e.stderr.decode()}")
		except Exception as e:
			print(f"An unexpected error occurred: {e}")


def parse_arguments():
	"""
	Parses command-line arguments for the file browser application.
	"""
	parser = argparse.ArgumentParser(
		description="""
		A file browser with the ability to preview
		images and caches using Gaffer's viewers. This
		is the same as the Browser panel from the main
		gui application, but running as a standalone
		application.
		"""
	)

	parser.add_argument(
		"--gui",
		action="store_true",
		help="Run application in GUI Mode.",
		default=False,
	)
	parser.add_argument(
		"--source",
		type=str,
		help="The source directory to process.",
		default="C:\\",
	)
	parser.add_argument(
		"--destination",
		type=str,
		help="The Out dir to inget the data for further processing within pipeline.",
		default="./",
		required=True,  # Assuming destination is always required based on the check
	)
	parser.add_argument(
		"--project",
		type=str,
		help="The name of the project.",
		default="gen63",
	)
	parser.add_argument(
		"--input_date",
		type=str,
		help="Date in YYYYMMDD format.",  # Changed format to be more standard
		required=True  # Make this argument mandatory
	)
	parser.add_argument(
		"--data_type",
		type=str,
		help="Search for specific file types (e.g., exr, jpg).",
		default="exr",
	)
	parser.add_argument(
		"--mov",
		action="store_true",
		help="Generate MOV files from exr.",
		default=False,
	)
	parser.add_argument(
		"--process",
		type=int,
		choices=[0, 1],
		help="1: Ingest (copy files into folder structure), 0: Egress (copy files out - not yet implemented).",
		default=1,
	)
	parser.add_argument(
		"--vendor",
		type=str,
		help="Optional: Vendor name to look into vendor or vendor/date directory.",
		default="",
	)
	parser.add_argument(
		"--hires",
		action="store_true",
		help="High resolution exrs.",
		default=False,
	)
	parser.add_argument(
		"--camera",
		type=str,
		help="Camera name.",
		default="",
	)
	parser.add_argument(
		"--take",
		type=str,
		help="Take number.",
		default="",
	)
	parser.add_argument(
		"--resolution",
		type=str,
		help="Resolution (e.g., 4448x3096).",
		default="4448x3096",
	)
	parser.add_argument(
		"--force",
		action="store_true",
		help="Force ingestion.",
		default=False,
	)
	parser.add_argument(
		"--proxy",
		type=str,
		help="Create a proxy file with the specified format (e.g., jpeg, png).",
		metavar="FORMAT",
	)

	args = parser.parse_args()
	return args

def main():
    
	args_dict = parse_arguments()
	processor = VFXFileProcessor(args_dict)
	processor.execute()

if __name__=="__main__":
    main()




