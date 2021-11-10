from upbankapi.models import Transaction
from datetime import datetime

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

	def to_generic_transaction_list(self,  sourceList):
		return [self.to_generic_transaction(source) for source in sourceList]

	def to_generic_transaction(self, source):
		if isinstance(source, Transaction):
			return self._create_from_up(source)
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
	
	def _create_from_csv(self, row):
		return GenericTransaction(row)