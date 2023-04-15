from __future__ import annotations

from datetime import datetime
from itertools import chain, combinations, product
from typing import List, Mapping, Callable, Union
from upbankapi.models import OwnershipType

from .config import Config, UpApiConfig
from .protocol import Account, Category, Client as ClientProtocol, Transaction
from .stream import StreamCollection
from .transaction import GenericTransaction, TransactionFilter, AccountType

import logging as log

class UpBankApiHelper:
	accounts : Mapping[str, Account]
	categories : Mapping[str, Category]
	client : ClientProtocol
	config : UpApiConfig

	def __init__(self, client : ClientProtocol, config : UpApiConfig):
		# Cache the accounts and categories to avoid triggering API rate-limit
		self.accounts = {account.id : account for account in client.accounts()}
		self.categories = {category.id : category for category in client.categories()}
		self.client = client
		self.config = config

	@staticmethod
	def account_type(account : Account):
		if account.ownership_type == OwnershipType.JOINT:
			return AccountType.JOINT
		if account.ownership_type == OwnershipType.INDIVIDUAL:
			return AccountType.PERSONAL

	def transactions(self, since : datetime, until : datetime):
		up_transactions = self.client.transactions(limit=self.config.limit,
										page_size=self.config.pagesize,
										since=since,
										until=until)
		return self.to_generic_transactions(up_transactions)

	def to_generic_transactions(self, transactionList : List[Transaction]):
		return [self.to_generic_transaction(source) for source in transactionList]

	def to_generic_transaction(self, transaction : Transaction):
		return GenericTransaction(
			date = transaction.created_at,
			description = transaction.description,
			amount = transaction.amount,
			currency = transaction.currency,
			source = self.source_account_type(transaction),
			destination = self.destination_account_type(transaction),
			category = self.category(transaction),
			parentCategory = self.parent_category(transaction),
			tags = transaction.tags,
			message = transaction.message
		)

	def source_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		id = relationships['account']['data']['id']
		return UpBankApiHelper.account_type(self.accounts[id])

	def destination_account_type(self, transaction : Transaction):
		relationships = transaction._raw_response['relationships']
		if relationships['transferAccount']['data']:
			id = relationships['transferAccount']['data']['id']
			if id in self.accounts:  # Check if transaction involves someone else's upbank account
				return UpBankApiHelper.account_type(self.accounts[id])
			if self.config.joint.partner_accounts.contains(transaction.description):
					return AccountType.PARTNER
		return AccountType.EXTERNAL

	def category(self, transaction : Transaction):
		if transaction.category:
			return self.categories[transaction.category.id].name
		return None

	def parent_category(self, transaction : Transaction):
		if transaction.category and transaction.category.parent:
			return self.categories[transaction.category.parent.id].name
		return None


class TransactionCollection:
	config : Config
	transactions : List[GenericTransaction]

	def __init__(self, config : Config):
		self.config = config
		self.transactions = list()
		pass

	def add_from_up_api(self, client : ClientProtocol) -> None:
		helper = UpBankApiHelper(client, self.config.up_api)
		transactions = helper.transactions(self.config.since, self.config.until)
		self.add_transactions(transactions)
		pass

	def add_transactions(self, transactions : List[GenericTransaction]) -> None:
		self._update_relations(transactions)
		self.transactions.extend(transactions)
		# self._try_combine()
		self._update_joint_transaction_splits()
		pass

	def _update_relations(self, new_transactions : List[Transaction]) -> None:
		with_existing_transactions = product(self.transactions, new_transactions)
		with_new_transactions = combinations(new_transactions, 2)
		for t1, t2 in chain(with_existing_transactions, with_new_transactions):
			if t1.relates_to(t2):
				t1.connect(t2)
		pass

	def _try_combine(self) -> None:
		# TODO: Handle case where two transactions have the same value but only one should be combined
		combinables = self.filter(lambda t: t.is_combinable)
		log.debug(f'Found {len(combinables)} combinable transactions')
		for root in combinables:
			root.update_using_connections()
			for t in root.connections:
				log.debug(f'Removing transaction {t}')
				self.transactions.remove(t)
			root.clear_connections()
		pass

	def _update_joint_transaction_splits(self) -> None:
		joint_transactions = self.filter(lambda t: t.source == AccountType.JOINT)
		personal_funding_total = sum(t.amount for t in joint_transactions if t.destination == AccountType.PERSONAL)
		partner_funding_total = sum(t.amount for t in joint_transactions if t.destination == AccountType.PARTNER)
		funding_total = personal_funding_total + partner_funding_total
		if funding_total != 0:
			for t in joint_transactions:
				if t.destination == AccountType.EXTERNAL:
					t.split = personal_funding_total / (personal_funding_total + partner_funding_total)
		pass

	def filter(self, filter: Union[TransactionFilter, Callable[[GenericTransaction], bool]]) -> List[GenericTransaction]:
		if isinstance(filter, Callable):
			filter = TransactionFilter(predicate=filter)
		return filter.filter(self.transactions)

	def as_streams(self) -> StreamCollection:
		streams = StreamCollection(self.config.collections)
		streams.add_transactions(self.transactions)
		return streams.cleanup().link()


if __name__ == '__main__':
	config = Config()  # use defaults
	transactions = TransactionCollection(config)

	first = GenericTransaction(description='main', amount=-10, category='this has a category')
	cover = GenericTransaction(description='cover from', amount=10)
	real = GenericTransaction(description='cover to', amount=-10)

	transactions.add_transactions([first, cover, real])
	for t in transactions.transactions:
		print(t, t.category)
