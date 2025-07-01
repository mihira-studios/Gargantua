import os
import logging
import concurrent.futures

from .ingestion_utils import generate_sequence_output_paths
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
)


class SequenceBuilder:
    def __init__(self, sequence, copy_op, proxy_op, mov_op):
        self.sequence = sequence  # dict with 'paths' key
        self.copy_op = copy_op
        self.proxy_op = proxy_op
        self.mov_op = mov_op
        self.copied_paths = []
        self.out_paths = {}

    def copy_sequence(self, metadata):
        copied = []
        start_frame = metadata.get('start_frame', 1001) # Default start frame
        overwrite = metadata.get('overwrite', False)
        if not self.sequence or not self.sequence.get('paths'):
            logging.error("No valid sequence paths found.")
            return  
        frame_counter = start_frame
        tasks = []

        num_workers = os.cpu_count() or 4  # Fallback to 4 if detection fails

        out_paths = {}
        for src in sorted(self.sequence['paths']):
            out  = generate_sequence_output_paths(self.sequence, metadata, frame_number=frame_counter, ext='exr')
            if not out:
                logging.error("Failed to generate output paths for the sequence.")
                return
            out_paths[src]  = out
            frame_counter += 1  
        
        logging.info(f"Output paths generated: {out_paths}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            for src in sorted(self.sequence['paths']):
                _, ext = os.path.splitext(os.path.basename(src))
                plate_path = out_paths[src]['plate']
                # Submit each copy as a parallel task
                tasks.append(executor.submit(self.copy_op.execute, src, plate_path, overwrite))
                copied.append(plate_path)
               
            # Wait for all copies to finish
            for task in concurrent.futures.as_completed(tasks):
                task.result()
        self.copied_paths = copied

        # Feedback after all files in the sequence are copied
        folder_name = os.path.dirname(plate_path)
        logging.info(f"Copy complete for sequence in folder: {folder_name} ({len(self.copied_paths)} files)")

    def generate_proxies(self):
        if not self.copied_paths:
            return
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for exr_path in self.copied_paths:
                proxy_path = os.path.join(self.out_paths['proxy'], os.path.basename(exr_path).replace('.exr', f'.{self.proxy_fmt}'))
                futures.append(executor.submit(self.proxy_op.execute, exr_path, proxy_path, self.proxy_fmt))
            for future in concurrent.futures.as_completed(futures):
                future.result()

    def generate_mov(self):
        if not self.copied_paths:
            return
        pattern = self.copied_paths[0].replace('1001', '%04d')  # adjust as needed
        mov_path = os.path.join(self.out_paths['mov'], os.path.basename(pattern).replace('exr', 'mov'))
        self.mov_op.execute(pattern, mov_path)

    def build(self, parallel_proxy=False, metadata= None):
        self.copy_sequence(metadata)
        if metadata.get('proxy_format') and parallel_proxy:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                executor.submit(self.generate_proxies, metadata.get('proxy_format'))
                executor.submit(self.generate_mov)
        else:
            if metadata.get('proxy'):
                self.generate_proxies()
            if metadata.get('mov'):
                self.generate_mov()