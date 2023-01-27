import datetime
import unittest
from src.config import Config, CollectionConfig, ClassifierConfig, TransactionType
from src.transaction import GenericTransaction, TransactionFactory

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
	date = datetime.now(),
	description = 'default',
	amount = 10,
	currency = 'AUD',
)

class TestConfig(unittest.TestCase):
	def test_classifier_alias(self):
		config = ClassifierConfig(defaultClassifiers['tags'])
		self.assertEqual(config.get_alias('tag1'), 'alias')
		self.assertEqual(config.get_alias('tag2'), None)
		self.assertEqual(config.get_alias('expected_missing_tag'), None)

	def test_collection_alias(self):
		config = CollectionConfig(defaultCollection, TransactionType.Income)
		transaction = defaultTransaction
		transaction.tags = ['tag1', 'tag2']
		self.assertEqual(config.get_alias(transaction), 'alias')

	def test_classifier_contains(self):
		config = ClassifierConfig(defaultClassifiers['tags'])
		self.assertEqual(config.contains('tag1'), True)
		self.assertEqual(config.contains('tag2'), True)
		self.assertEqual(config.contains('expected_missing_tag'), False)

	def test_collection_match(self):
		config = CollectionConfig(defaultCollection, TransactionType.Income)
		self.assertEqual(config.match(defaultTransaction), False)
		transaction = defaultTransaction
		transaction.tags = ['tag1']
		self.assertEqual(config.match(defaultTransaction), True)
		

if __name__ == '__main__':
	unittest.main()
