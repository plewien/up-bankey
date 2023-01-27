import csv
from upbankapi.models import Transaction
from datetime import datetime
from numbers import Number
from typing import Optional

from .category import Categories

# 1. Obtain data from source(s)
# 2. Read into generic transaction array
# 3. Parse into streams
# 4. Format into SankeyMatic

class GenericTransaction:

	def __init__(self, date, description, amount, currency, category=None, parentCategory=None, tags=list(), message=None):
		self.date: datetime = date
		self.description: str = description
		self.amount: float = amount
		self.currency: str = currency
		self.category: Optional[str] = category
		self.parentCategory: Optional[str] = parentCategory
		self.tags: list[str] = tags
		self.message: Optional[str] = message

	def __repr__(self):
		return f"<Transaction {self.date}: {self.amount} {self.currency} [{self.description}]>"


class TransactionFactory:

	def __init__(self, categories : Categories):
		self.categories = categories
		pass

	def to_generic_transactions(self, sourceList):
		return [self.to_generic_transaction(source) for source in sourceList]

	def to_generic_transaction(self, *argv):
		if isinstance(argv[0], Transaction):
			return self._create_from_up(argv[0])
		if len(argv) == 2 and isinstance(argv[0], Number) and isinstance(argv[1], str):
			return self._create_from_value(argv[0], argv[1])
		print("Warning: No matching transaction type found for arguments", str(argv))
		return None

	def _categorify(self, id):
		if id in self.categories:
			return self.categories[id].name
		return id

	def _create_from_up(self, transaction : Transaction):
		# Support for tags and categories is missing from the API Python wrapper, but there is an
		# open pull request https://github.com/jcwillox/up-bank-api/pull/3. When this is merged,
		# the manual creation of tags and categories here can be simplified.
		relationships = transaction.raw["relationships"]
		category = (relationships["category"]["data"]["id"]
			if relationships["category"]["data"]
            else None)
		parentCategory = (relationships["parentCategory"]["data"]["id"]
			if relationships["parentCategory"]["data"]
            else None)
		tags = [ tag["id"] for tag in relationships["tags"]["data"] ]

		return GenericTransaction(
			date = transaction.created_at,
			description = transaction.description,
			amount = transaction.amount,
			currency = transaction.currency,
			category = self._categorify(category),
			parentCategory = self._categorify(parentCategory),
			tags = tags,
			message = transaction.message
		)

	def _create_from_value(self, amount : float, description):
		return GenericTransaction(
			date = datetime.now(),
			description = description,
			amount = amount,
			currency = "AUD"  # TODO: Default currency
		)

	def _create_from_csv(self, row : csv):
		category = translate(row[self.csv.index['category']])
		return GenericTransaction(
			date = row[self.csv.index['date']],
			description = row[self.csv.index['description']],
			amount = row[self.csv.index['amount']],
			currency = config.currency,
			category = category.self,
			parentCategory = category.parent
		)
