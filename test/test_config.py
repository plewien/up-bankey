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

class TestConfig(unittest.TestCase):
	def test_classifier_alias(self):
		config = ClassifierConfig(defaultClassifiers['tags'])
		self.assertEqual(config.get_alias('tag1'), 'alias')
		self.assertEqual(config.get_alias('tag2'), None)
		self.assertEqual(config.get_alias('expected_missing_tag'), None)

	def test_collection_alias(self):
		config = CollectionConfig(defaultCollection, TransactionType.Income)
		transaction = TransactionFactory(None).to_generic_transaction(100, 'transaction')
		transaction.tags = ['tag1', 'tag2']
		self.assertEqual(config.get_alias(transaction), 'alias')

if __name__ == '__main__':
	unittest.main()
