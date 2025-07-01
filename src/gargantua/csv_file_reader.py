
import csv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'
)



class MVLCSVReader:
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
			logging.info(f"Error: File not found at '{self.file_path}'")
			return []
		except Exception as e:
			logging.info(f"Error reading CSV file: {e}")
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
			logging.info("Warning: No data has been read from the CSV file.")
			return mapping

		if key_column_index < 0 or (self.data and key_column_index >= len(self.data[0])):
			logging.info(f"Error: Key column index {key_column_index} is out of bounds.")
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
			logging.info("Warning: No data has been read from the CSV file.")
			return mapping

		if not self.header and skip_header:
			logging.info("Error: Header not read. Call read_csv() with skip_header=True first.")
			return mapping

		try:
			key_column_index = self.header.index(key_column_name)
			mapping = self.create_dictionary_mapping(key_column_index=key_column_index, skip_header=True)
		except ValueError:
			logging.info(f"Error: Key column '{key_column_name}' not found in the header.")
		return mapping