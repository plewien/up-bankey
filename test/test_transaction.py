import unittest
import copy
from src.config import CollectionConfig
from src.transaction import GenericTransaction, TransactionAliaser, TransactionMatcher

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
		

if __name__ == '__main__':
	unittest.main()
