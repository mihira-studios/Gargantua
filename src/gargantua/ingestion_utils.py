
import os
import re
import logging
#import OpenEXR
#import Imath

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
)

def generate_sequence_output_paths(seq, metadata, frame_number=1001, ext='exr'):
    current_shot = seq.get("shot")
    if not current_shot:
        logging.error("No current shot found in the sequence.")
        return

    current_scene = seq.get("scene")
    if not current_scene:
        logging.error("No current scene found in the sequence.")
        return  

    current_resolution = seq.get("resolution")
    if not current_resolution:
        logging.error("No current resolution found in the sequence.")
        return
    
    current_project = metadata.get("project")
    if not current_project:	
        logging.error("No current project found in the metadata.")
        return	
    
    destination = metadata.get("destination")
    if not destination:
        logging.error("No destination found in the metadata.")
        return	
    

    matching_key = None

    parts = None

    matching_key = None
    for key in metadata.keys():
        if current_scene in key:
            parts = key.split('/')
            if len(parts) != 2:
                continue
            _, shot = parts
            if current_shot == shot:
                matching_key = key
                break

    if not matching_key:
        logging.error(f"generate_output_paths : No matching key found for scene {current_scene} and shot {current_shot}")
        exit(1)
    if not metadata.get(matching_key):
        logging.error(f"generate_output_paths : No metadata found for key {matching_key}")
        exit(1)	

    scene_shot_data = metadata[matching_key][0]  # e.g. GEN63_SC_48_SH_0160
    scene_shot_type = metadata[matching_key][1]  # e.g. _main_plate_v001
    parts = [p for p in scene_shot_type.split('_') if p] 
    variant = product_type = version = None
    if len(parts) == 3:
        variant = parts[0] 
        product_type = parts[1] 
        version = parts[2] 
    elif len(parts)  == 2:
        variant = parts[0]
        version = parts[1]
        product_type = ""
        
	# {project_root}/work/sequences/{sequence}/{shot}/{step}/{task}/{user}/{dcc}/{name}
    current_base_path = os.path.join(destination, current_project, "work", "sequences", f"SC_{current_scene}", f"SH_{scene_shot_data.split('_')[-1]}")    
    frame = str(frame_number).zfill(4)  # Pad frame number with leading zeros
    filename = generate_out_filename(frame, ext, scene_shot_data, scene_shot_type, current_resolution)
    plate_path = os.path.join(current_base_path, variant, product_type, version)
    proxy_path = os.path.join(current_base_path, variant, 'proxy', version)
    mov_path = os.path.join(current_base_path, variant, 'mov', version)
    output_paths = { 
        'plate': os.path.join(plate_path, filename),
        'proxy': proxy_path,
        'mov': mov_path  
    }
    return output_paths
			
def generate_out_filename(frame, ext, sceneshot=None, type=None, resolution=None):
    """
    Generates a new filename based on the provided file information.

    Args:
        file_info (dict): A dictionary containing file information.

    Returns:
        str: The new filename.
    """

    filename_placeholder = "{sceneshot}_{type}_{frame_number}_f{resolution}.{ext}"
    file_data = {
        "sceneshot": sceneshot,
        "type": type,
        "frame_number": frame,
        "resolution": resolution,
        "ext": ext,
    }

    filename = filename_placeholder.format(**file_data)
    return filename

def check_missing_frames(paths):
    """
    Checks for missing frames in the given files and sequences.

    Args:
        paths (list): list of file with frame numbers

    Returns:
        bool: True if there is a missing frame, False otherwise.
    """
    frame_numbers = []
    for path in paths:
        try:
            frame_number = int(os.path.splitext(os.path.basename(path))[0].split('_')[-1])
            frame_numbers.append(frame_number)
        except Exception as e:
            logging.info(f"Error extracting frame number from {os.path.basename(path)}: {e}")
    if not frame_numbers:
        logging.info(f"Could not find any frame numbers at path {path}")
        return True

    frame_numbers.sort()
    missing = [f for f in range(frame_numbers[0], frame_numbers[-1] + 1) if f not in frame_numbers]
    if missing:
        logging.info(f"frames missing: {missing}")
        return True

    return False

def get_files_and_sequences(root_dirs, scene=None, shot=None, resolution=None):
    """
    Reads a directory and identifies individual files and file sequences.
    Returns:
        tuple: A tuple containing two lists:
            - files (list): A list of individual file paths.
            - sequences (list): A list of dictionaries representing file sequences.
    """
    files = []
    sequences = []
    # Matches: basename_frame.ext (frame is one or more digits)
    sequence_regex = re.compile(r"^(.+?)_(\d+)\.([a-zA-Z0-9]+)$")

    if not isinstance(root_dirs, list):
        root_dirs = [root_dirs]

    for root_dir in root_dirs:
        all_items = sorted([os.path.join(root_dir, item) for item in os.listdir(root_dir)])
        # Group files by (base_name, extension, padding)
        seq_groups = {}
        for item_path in all_items:
            if os.path.isfile(item_path):
                match = sequence_regex.match(os.path.basename(item_path))
                if match:
                    base_name, frame_number_str, extension = match.groups()
                    padding = len(frame_number_str)
                    key = (base_name, extension, padding)
                    seq_groups.setdefault(key, []).append((int(frame_number_str), item_path))
                else:
                    files.append(item_path)
        # Now process the groups
        for (base_name, extension, padding), frames in seq_groups.items():
            if len(frames) > 1:
                frames_sorted = sorted(frames)
                sequence_files = [f[1] for f in frames_sorted]
                start_frame = frames_sorted[0][0]
                end_frame = frames_sorted[-1][0]
                sequences.append({
					'scene': scene,
					'shot': shot,
                    'base_name': base_name,
                    'padding': padding,
                    'start': start_frame,
                    'end': end_frame,
                    'extension': extension,
                    'paths': sequence_files,
					'resolution': resolution
                })
            else:
                # Only one file with this pattern, treat as single file
                files.append(frames[0][1])

    return files, sequences

# def add_src_path_to_exr(exr_path, src_path):
#     file = OpenEXR.InputFile(exr_path)
#     header = file.header()
#     header['srcPath'] = src_path.encode('utf-8')
#     # You would need to write a new EXR file with this header and the original data
#     # This is advanced and not typical for most pipelines