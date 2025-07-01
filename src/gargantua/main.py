
import argparse
from .ingestion_processor import MVLIngestionProcessor

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
		"--proxy_format",
		type=str,
		help="Create a proxy file with the specified format (e.g., jpeg, png).",
		metavar="FORMAT",
	)

	args = parser.parse_args()
	return args

def main():
	args = parse_arguments()
	processor = MVLIngestionProcessor(args)
	processor.execute()

if __name__=="__main__":
    main()




