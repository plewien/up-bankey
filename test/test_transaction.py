import unittest
import copy
from src.config import CollectionConfig
from src.transaction import GenericTransaction, TransactionAliaser, TransactionMatcher, AccountType

defaultClassifiers = {
	'tags': [{'tag1': 'alias'}, 'tag2'],
	'accounts': [{'account1': 'alias'}, 'account2'],
}

defaultThreshold = {
	'count': 10,
	'value': 0,
	'percentage': 0
}

defaultCollection = {
	'name' : 'Name',
	'outgoing' : False,
	'classifiers' : defaultClassifiers,
	'threshold' : defaultThreshold
}

defaultTransaction = GenericTransaction(
	description = 'default',
	amount = 10,
)

class TestTransaction(unittest.TestCase):
	def test_collection_alias(self):
		config = CollectionConfig(defaultCollection)
		transaction = copy.deepcopy(defaultTransaction)
		transaction.tags = ['tag1', 'tag2']
		self.assertEqual(TransactionAliaser(config).get_alias(transaction), 'alias')

	def test_collection_match(self):
		config = CollectionConfig(defaultCollection)
		matcher = TransactionMatcher(config)
		transaction = copy.deepcopy(defaultTransaction)
		self.assertEqual(matcher.match(transaction), False)
		transaction.tags = ['tag1']
		self.assertEqual(matcher.match(transaction), True)


class TestGenericTransaction(unittest.TestCase):
	def test_transaction_internal(self):
		transaction = copy.deepcopy(defaultTransaction)
		transaction.source = AccountType.PERSONAL
		transaction.destination = AccountType.PERSONAL
		self.assertEqual(transaction.internal, True)
		for dest in [AccountType.JOINT, AccountType.EXTERNAL]:
			transaction.destination = dest
			self.assertEqual(transaction.internal, False)

	def test_transaction_equal(self):
		transaction = copy.deepcopy(defaultTransaction)
		self.assertEqual(transaction, defaultTransaction)

	def test_flipped_transaction_equal(self):
		transaction = GenericTransaction(
			description = 'default',
			amount = 10,
			source = AccountType.PERSONAL,
			destination = AccountType.EXTERNAL,
		)
		transaction2 = GenericTransaction(
			description = 'default',
			amount = -10,
			source = AccountType.EXTERNAL,
			destination = AccountType.PERSONAL
		)
		self.assertEqual(transaction, transaction2)


if __name__ == '__main__':
	unittest.main()
