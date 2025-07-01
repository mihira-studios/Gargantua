import os
import shutil
import subprocess
import ffmpeg
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
)

class FileOperation:
    """Base class for file operations."""
    def execute(self, *args, **kwargs):
        raise NotImplementedError

class CopyFileOperation(FileOperation):
    def execute(self, src, dst, overwrite=False):
        if os.path.exists(dst) and os.path.getsize(dst) > 0 and os.path.getsize(src) > 0 and not overwrite:
            logging.info(f"Skipped copy (already exists): {os.path.basename(dst)}")
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

        # Validate file sizes
        src_size = os.path.getsize(src)
        dst_size = os.path.getsize(dst)
        if src_size == dst_size:
            logging.info(f"Copied file: {os.path.basename(src)} to {dst} (size validated)")
        else:
            logging.warning(f"Size mismatch for {src} -> {dst}: src={src_size}, dst={dst_size}")
        


class ProxyGenerationOperation(FileOperation):
    def execute(self, input_path, output_path, fmt):
        fmt = fmt.lower()
        if fmt not in ["jpeg", "png"]:
            logging.info(f"Unsupported format: {fmt}")
            return
        command = [
            "openimageio", "convert", input_path,
            "-o", output_path, "-format", fmt
        ]
        logging.info(f"Generating proxy: {' '.join(command)}")
        try:
            subprocess.run(command, check=True, capture_output=True)
            logging.info(f"Proxy generated: {output_path}")
        except Exception as e:
            logging.info(f"Proxy generation failed: {e}")

class MovGenerationOperation(FileOperation):
    def execute(self, input_pattern, output_mov, fps=24):
        logging.info(f"Generating MOV: {output_mov} from {input_pattern}")
        (
            ffmpeg.input(input_pattern, framerate=fps)
            .output(output_mov, vcodec='prores_ks', pix_fmt='yuv422p10le')
            .overwrite_output()
            .run()
        )