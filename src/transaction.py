from upbankapi.models import Transaction
from datetime import datetime
from numbers import Number

# 1. Obtain data from source(s)
# 2. Read into generic transaction array
# 3. Parse into streams
# 4. Format into SankeyMatic

class GenericTransaction(Transaction):

	def __init__(self, date, description, amount, currency, category=None, parentCategory=None, tags=None, message=None):
		self.date: datetime = date
		self.description: str = description
		self.amount: float = amount
		self.currency: str = currency
		self.category: str = category
		self.parentCategory: str = parentCategory
		self.tags: list = tags
		self.message: str = message

	def __repr__(self):
		return f"<Transaction {self.date}: {self.amount} {self.currency} [{self.description}]>"


class TransactionFactory:

	def to_generic_transaction_list(self, sourceList):
		return [self.to_generic_transaction(source) for source in sourceList]

	def to_generic_transaction(self, *argv):
		if isinstance(argv[0], Transaction):
			return self._create_from_up(argv[0])
		if len(argv) == 2 and isinstance(argv[0], Number) and isinstance(argv[1], str):
			return self._create_from_value(argv[0], argv[1])
		print("Warning: No matching transaction type found for arguments", str(argv))
		print(len(argv))
		return None

	def _create_from_up(self, transaction : Transaction):
		return GenericTransaction(
			date = transaction.created_at,
			description = transaction.description,
			amount = transaction.amount,
			currency = transaction.currency,
			category = transaction.category,
			parentCategory = transaction.parentCategory,
			tags = transaction.tags,
			message = transaction.message
		)

	def _create_from_value(self, amount : float, description):
		return GenericTransaction(
			date = datetime.now(),
			description = description,
			amount = amount,
			currency = "AUD"  # TODO: Default currency
		)

	def _create_from_csv(self, row):
		return GenericTransaction(row)