from __future__ import annotations

from .config import CollectionConfig, TransactionType
from .protocol import Transaction
from datetime import datetime
from typing import Optional, List, Mapping, Callable
from enum import Enum
import copy

class AccountType(str, Enum):
	JOINT = 'JOINT'
	PARTNER = 'PARTNER'
	PERSONAL = 'PERSONAL'
	EXTERNAL = 'EXTERNAL'


class GenericTransaction(Transaction):
	description: str
	amount: float
	_split: float
	currency: str
	date: datetime
	source: Optional[AccountType]
	destination: Optional[AccountType]
	category: Optional[str]
	parentCategory: Optional[str]
	tags: List[str]
	message: Optional[str]
	_relations: set[GenericTransaction]

	def __init__(self,
			description,
			amount,
			currency="AUD",
			date=datetime.now(),
			source=None,
			destination=None,
			category=None,
			parentCategory=None,
			tags=list(),
			message=None):
		self.description = description
		self.amount = amount
		self.currency = currency
		self.date = date
		self.source = source
		self.destination = destination
		self.category = category
		self.parentCategory = parentCategory
		self.tags = tags
		self.message = message
		self._relations = set()
		self._split = 1.0

	def __repr__(self):
		return f"<Transaction {self.date}: {self.amount} {self.currency} [{self.description}]>"

	def __eq__(self, other) -> bool:
		if type(other) is type(self):
			return self.__dict__ == other.__dict__
		return False

	def __hash__(self):
		return hash((self.description, self.date, self.amount))

	@property
	def total(self) -> float:
		if self.internal:
			return 0
		return self._split * self.amount

	@property
	def internal(self) -> bool:
		return self.source == self.destination

	@property
	def outgoing(self) -> bool:
		return self.involves_account(AccountType.EXTERNAL)

	@property
	def split(self) -> float:
		return self._split

	@split.setter
	def split(self, split : float) -> None:
		assert(split > 0 and split < 1)
		assert(self.involves_account(AccountType.JOINT))
		self._split = split

	def involves_account(self, account : AccountType):
		return (self.source == account) ^ (self.destination == account)

	def connect(self, other : GenericTransaction) -> None:
		other._relations.add(self)
		self._relations.add(other)

	def clear_connections(self) -> None:
		self._relations = set()

	@property
	def is_combinable(self) -> bool:
		return len(self._relations) >= 2 \
			and self.involves_account(AccountType.EXTERNAL) \
			and any(t.involves_account(AccountType.PERSONAL) for t in self._relations) \
			and any(t.involves_account(AccountType.JOINT) for t in self._relations)

	@property
	def connections(self) -> List[GenericTransaction]:
		return list(self._relations)

	@property
	def root_transaction(self) -> GenericTransaction:
		# only the root transaction has a category
		for t in self._relations | {self}:
			if t.involves_account(AccountType.EXTERNAL):
				return t
		raise RuntimeError("No root transaction found")

	def update_using_connections(self) -> None:
		# 
		for transaction in self._relations:
			if self.amount == transaction.amount:
				self.source = transaction.source

	def relates_to(self, other : GenericTransaction) -> bool:
		return self.matches(other) or self.covers_or_covered(other)

	def matches(self, other : GenericTransaction) -> bool:
		return self.amount == -1 * other.amount 	\
			and self.currency == other.currency 	\
			and self.source == other.destination 	\
			and self.destination == other.source

	def covers(self, other : GenericTransaction) -> bool:
		return self.covers_or_covered(other) 		\
			and self.date >= other.date

	def covers_or_covered(self, other : GenericTransaction) -> bool:
		return abs(self.amount) == abs(other.amount) \
			and "cover" in (self.description + other.description).lower()

	def between_accounts(self, account : AccountType, other_account : AccountType) -> bool:
		return (self.source == account and self.destination == other_account) or \
				(self.source == other_account and self.destination == account)


class TransactionAliaser:
	def __init__(self, config : CollectionConfig):
		self.config = config

	def get_alias(self, transaction : GenericTransaction):
		alias = self.get_alias_by_tag(transaction)
		if alias is not None:
			return alias
		alias = self.get_alias_by_account(transaction)
		if alias is not None:
			return alias
		return transaction.description

	def get_alias_by_tag(self, transaction : GenericTransaction):
		return next((self.config.tags.get_alias(tag) for tag in transaction.tags), None)
	
	def get_alias_by_account(self, transaction : GenericTransaction):		
		return self.config.accounts.get_alias(transaction.description)


class TransactionFilter:
	accounts: List[str]
	sources: List[AccountType]
	destinations: List[AccountType]
	categories: List[str]
	tags: List[str]
	predicate: Callable[[Transaction], bool]

	def __init__(self,
			accounts=list(),
			sources=list(),
			destinations=list(),
			categories=list(),
			tags=list(),
			predicate=lambda _: True):
		self.accounts = accounts
		self.sources = sources
		self.destinations = destinations
		self.categories = categories
		self.tags = tags
		self.predicate = predicate

	def filter(self, transactions : List[GenericTransaction]):
		return [t for t in transactions if self.match_all(t)]

	def match_all(self, transaction : GenericTransaction) -> bool:
		if self.tags and not self.match_by_tag(transaction):
			return False
		if self.accounts and not self.match_by_account(transaction):
			return False
		if self.sources and not self.match_by_source(transaction):
			return False
		if self.destinations and not self.match_by_destination(transaction):
			return False
		if self.categories and not self.match_by_category(transaction):
			return False
		return self.predicate(transaction)

	def match_any(self, transaction : GenericTransaction) -> bool:
		return self.match_by_tag(transaction)			\
			or self.match_by_account(transaction)		\
			or self.match_by_source(transaction)		\
			or self.match_by_destination(transaction)	\
			or self.match_by_category(transaction)		\
			or self.predicate(transaction)

	def match_by_tag(self, transaction : GenericTransaction) -> bool:
		return any([self.tags.contains(tag) for tag in transaction.tags])

	def match_by_account(self, transaction : GenericTransaction) -> bool:
		return self.accounts.contains(transaction.description)

	def match_by_source(self, transaction : GenericTransaction) -> bool:
		return self.sources.contains(transaction.source)

	def match_by_destination(self, transaction : GenericTransaction) -> bool:
		return self.destinations.contains(transaction.destination)

	def match_by_category(self, transaction : GenericTransaction) -> bool:
		return self.categories.contains(transaction.category)
	
	def match_by_custom_predicate(self, transaction : GenericTransaction) -> bool:
		return self.predicate(transaction)


class TransactionClassifier:
	filters : Mapping[TransactionType, TransactionFilter]

	def __init__(self, configs : Mapping[TransactionType, CollectionConfig]):
		self.filters = {type : TransactionFilter(accounts=config.accounts, tags=config.tags) for type, config in configs.items()}

	def classify(self, transaction : GenericTransaction) -> TransactionType:
		classifierOrder = [
			self.classify_by_tag,
			self.classify_by_category_presence,
			self.classify_by_source_and_destination,
			self.classify_by_account,
			self.classify_by_postive_value,
		]
		for classifier in classifierOrder:
			classification = classifier(transaction)
			if classification is not TransactionType.Unknown:
				return classification
		return TransactionType.Unknown

	def classify_by_tag(self, transaction : GenericTransaction) -> TransactionType:
		for type, filter in self.filters.items():
			if filter.match_by_tag(transaction):
				return type
		return TransactionType.Unknown

	def classify_by_account(self, transaction : GenericTransaction) -> TransactionType:
		for type, filter in self.filters.items():
			if filter.match_by_account(transaction):
				return type
		return TransactionType.Unknown

	def classify_by_source_and_destination(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.internal:
			return TransactionType.Ignore
		return TransactionType.Unknown

	def classify_by_category_presence(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.category:
			return TransactionType.Expense
		return TransactionType.Unknown

	def classify_by_postive_value(self, transaction : GenericTransaction) -> TransactionType:
		if transaction.amount > 0:
			return TransactionType.Income
		return TransactionType.Unknown
