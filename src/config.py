import yaml
import itertools
from enum import Enum
from .transaction import GenericTransaction
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta

def readYaml(filePath : str):
	with open(filePath, 'r') as f:
		return yaml.safe_load(f)

def toDateTime(input: str):
	if input is None:
		return None
	if input in {"today", "now"}:
		return datetime.now()
	if input.endswith("ago"):
		value, unit, _ = input.split()  # assumes format '1 year ago', etc
		if not unit.endswith('s'):
			unit += 's'  # plural necessary
		return datetime.now() - relativedelta(**{unit: int(value)})
	return parser.parse(input)

class TransactionType(Enum):
	Unknown     = -2
	Ignore		= -1
	Income		= 0
	Expense     = 1
	Savings     = 2


class ClassifierConfig:
	def __init__(self, config):
		self.collection = {}
		for element in config:
			self.add(element)

	def __str__(self):
		return str(self.collection)

	def __repr__(self):
		return repr(self.collection)

	def __bool__(self):
		return self.collection != {}

	def add(self, classification):
		if isinstance(classification, dict):
			self.collection.update(classification)
		else:
			self.collection[classification] = None

	def contains(self, name):
		return name in self.collection

	def get_alias(self, name):
		return self.collection.get(name, None)


class ThresholdConfig:
	def __init__(self, config):
		self.count = config['count']
		self.absolute = config['value']
		self.relative = config['percentage'] / 100


class CollectionConfig:
	def __init__(self, config, type):
		self.name = config['name']
		self.type = type
		self.tags = ClassifierConfig(config['classifiers']['tags'])
		self.accounts = ClassifierConfig(config['classifiers']['accounts'])
		self.threshold = ThresholdConfig(config['threshold'])
		self.outgoing = config['outgoing']

	def __str__(self):
		return "%s(tags=%s, accounts=%s)" % (
			self.name, self.tags, self.accounts)

	def __repr__(self):
		return "%s<name=%r, tags=(%r), accounts=(%r)>" % (
			self.__class__.__name__, self.name, self.tags, self.accounts)

	def get_alias(self, transaction : GenericTransaction):
		alias = self.get_alias_by_tag(transaction)
		if alias is not None:
			return alias
		alias = self.get_alias_by_account(transaction)
		if alias is not None:
			return alias
		return transaction.description

	def get_alias_by_tag(self, transaction : GenericTransaction):
		return next((self.tags.get_alias(tag) for tag in transaction.tags), None)
	
	def get_alias_by_account(self, transaction : GenericTransaction):		
		return self.accounts.get_alias(transaction.description)

	def match(self, transaction : GenericTransaction):
		return self.match_by_tag(transaction) or self.match_by_account(transaction)

	def match_by_tag(self, transaction : GenericTransaction):
		return any([self.tags.contains(tag) for tag in transaction.tags])

	def match_by_account(self, transaction : GenericTransaction):
		return self.accounts.contains(transaction.description)


class IgnoreConfig(CollectionConfig):
	def __init__(self, config):
		self.name = "Ignore"
		self.tags = ClassifierConfig(config['tags'])
		self.accounts = ClassifierConfig(config['accounts'])


class Config:
	def __init__(self, path=None):
		config = Config._readConfig(path)
		self.since = toDateTime(config['options']['dates']['since'])
		self.until = toDateTime(config['options']['dates']['until'])
		self.limit = config['options']['sources']['up-api']['limit']
		self.pagesize = config['options']['sources']['up-api']['pagesize']
		self.ignore = IgnoreConfig(config['ignore'])
		self.income = CollectionConfig(config['collections']['income'], TransactionType.Income)
		self.expense = CollectionConfig(config['collections']['expenses'], TransactionType.Expense)
		self.savings = CollectionConfig(config['collections']['savings'], TransactionType.Savings)

		# "Interest" will always be an income stream, so populate here
		self.income.accounts.add("Interest")

	def __str__(self):
		return "Dates:\n %s - %s\n" % (self.since, self.until) \
			+ "Collections:\n %s\n %s\n %s\n %s" % (
				self.income, self.expense, self.savings, self.ignore)

	def filter(self, transactions):
		print("%d transactions found" % len(transactions))
		if len(transactions) >= self.limit:
			print("Warning: Reached limit for number of transactions, consider increasing in configuration yaml")
		filtered = [t for t in transactions if not Config._isInternalTransaction(t)]
		warn = [t for t in filtered if self.ignore.match(t)]
		filtered = [t for t in filtered if not self.ignore.match(t)]
		print("%d transactions to be processed" % len(filtered))
		for t in warn:
			print("Ignoring transaction", t)
		return filtered

	@staticmethod
	def _readConfig(path):
		if path is None:
			return defaultConfig
		config = readYaml(path)
		Config._populateRecursively(config, defaultConfig)
		return config

	# Inspired by https://stackoverflow.com/questions/36831998/how-to-fill-default-parameters-in-yaml-file-using-python
	@staticmethod
	def _populateRecursively(input: dict, default):
		for k in default:
			if isinstance(default[k], dict):  # populate the sub-config
				Config._populateRecursively(input.setdefault(k, {}), default[k])
			else:
				input.setdefault(k, default[k])

	@staticmethod
	def _isInternalTransaction(transaction: GenericTransaction):
		actions = ['Cover', 'Transfer', 'Forward', 'Quick save transfer']
		directions = ['from', 'to']
		internalDescriptions = ['%s %s ' % (a, d) for a, d in itertools.product(actions, directions)]
		internalDescriptions += ['Round Up', 'Bonus Payment']
		return transaction.description.startswith(tuple(internalDescriptions))

	def classify(self, transaction : GenericTransaction):
		classifierOrder = [
			self.classify_by_tag,
			self.classify_by_category_presence,
			self.classify_by_account,
			self.classify_by_postive_value,
		]
		for classifier in classifierOrder:
			classification = classifier(transaction)
			if classification is not TransactionType.Unknown:
				return classification

		return TransactionType.Unknown

	def classify_by_tag(self, transaction : GenericTransaction):
		for collection in (self.income, self.expense, self.savings):
			if collection.match_by_tag(transaction):
				return collection.type
		return TransactionType.Unknown

	def classify_by_account(self, transaction : GenericTransaction):
		for collection in (self.income, self.expense, self.savings):
			if collection.match_by_account(transaction):
				return collection.type
		return TransactionType.Unknown

	def classify_by_category_presence(self, transaction : GenericTransaction):
		if transaction.category:
			return TransactionType.Expense
		return TransactionType.Unknown

	def classify_by_postive_value(self, transaction : GenericTransaction):
		if transaction.amount > 0:
			return TransactionType.Income
		return TransactionType.Unknown


defaultClassifier = {
	'tags': [],
	'accounts': [],
}

defaultThreshold = {
	'count': 10,
	'value': 0,
	'percentage': 0
}

defaultConfig = {
	'options': {
		'output': 'results.txt',
		'dates': {
			'since' : '1 year ago',
			'until': 'today'
		},
		'sources': {
			'up-api' : {
				'token' : 'UP_TOKEN',
				'limit' : 1000,
				'pagesize' : 100,
			}
		}
	},
	'collections' : {
		'income': {
			'name' : 'Income',
			'outgoing' : False,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'expenses': {
			'name' : 'Expenses',
			'outgoing' : True,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		},
		'savings': {
			'name' : 'Savings',
			'outgoing' : True,
			'classifiers' : defaultClassifier,
			'threshold' : defaultThreshold
		}
	},
	'ignore': defaultClassifier
}


if __name__ == "__main__":
	print("This is the example config:")
	config = Config("config/example.yaml")
	print(config)
