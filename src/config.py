import yaml
import itertools
from enum import Enum
from transaction import GenericTransaction
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta

def readYaml(filePath : str):
	with open(filePath, 'r') as f:
		return yaml.safe_load(f)

# Inspired by https://stackoverflow.com/questions/36831998/how-to-fill-default-parameters-in-yaml-file-using-python
def populateConfigRecursively(input: dict, default):
	for k in default:
		if isinstance(default[k], dict):  # populate the sub-config
			populateConfigRecursively(input.setdefault(k, {}), default[k])
		else:
			input.setdefault(k, default[k])

def toDateTime(input: str):
	if input is None:
		return None
	if input == "today" or input == "now":
		return datetime.now()
	if input.endswith("ago"):
		value, unit, _ = input.split()  # assumes format '1 year ago', etc
		return datetime.now() - relativedelta(**{unit: int(value)})
	return parser.parse(input)

class TransactionType(Enum):
	Unknown     = -2
	Ignore		= -1
	Income		= 0
	Expense     = 1
	Savings     = 2


class CollectionConfig:
	def __init__(self, config):
		self.name = config['name']
		self.tags = CollectionConfig.make_set(config['classifiers']['tags'])
		self.accounts = CollectionConfig.make_set(config['classifiers']['accounts'])
		self.tagAliases: dict = CollectionConfig.make_aliases(config['classifiers']['tags'])
		self.accountAliases: dict = CollectionConfig.make_aliases(config['classifiers']['accounts'])
		self.countThreshold = config['threshold']['count']
		self.absoluteThreshold = config['threshold']['value']
		self.relativeThreshold = config['threshold']['percentage'] / 100
		self.outgoing = config['outgoing']

	@staticmethod
	def make_set(l : list):
		s = set()
		for elem in l:
			if isinstance(elem, dict):
				for k in elem.keys():
					s.add(k)
			else:
				s.add(elem)
		return s

	@staticmethod
	def make_aliases(l : list):
		listOfAliases = filter(lambda e: isinstance(e, dict), l)
		return {k:v for element in listOfAliases for (k,v) in element.items()}

	def get_alias(self, transaction : GenericTransaction):
		for tag in transaction.tags:
			alias = self.tagAliases.get(tag, None)
			if alias is not None:
				return alias

		alias = self.accountAliases.get(transaction.description, None)
		if alias is not None:
			return alias

		return transaction.description

	def match_by_tag(self, transaction : GenericTransaction):
		return bool(self.tags.intersection(transaction.tags))

	def match_by_account(self, transaction : GenericTransaction):
		return transaction.description in self.accounts

	def match(self, transaction : GenericTransaction):
		return self.match_by_tag(transaction) or self.match_by_account(transaction)

class IgnoreConfig(CollectionConfig):
	def __init__(self, config):
		self.tags = CollectionConfig.make_set(config['tags'])
		self.accounts = CollectionConfig.make_set(config['accounts'])

class Config:
	def __init__(self, path):
		config = readYaml(path)
		populateConfigRecursively(config, defaultConfig)
		self.since = toDateTime(config['options']['dates']['since'])
		self.until = toDateTime(config['options']['dates']['until'])
		self.limit = config['options']['sources']['up-api']['limit']
		self.pagesize = config['options']['sources']['up-api']['pagesize']
		self.ignore = IgnoreConfig(config['ignore'])
		self.income = CollectionConfig(config['collections']['income'])
		self.expense = CollectionConfig(config['collections']['expenses'])
		self.savings = CollectionConfig(config['collections']['savings'])
		self._config = config

		# "Interest" will always be an income stream, so populate here
		self.income.accounts.add("Interest")

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
		if self.income.match_by_tag(transaction):		return TransactionType.Income
		if self.expense.match_by_tag(transaction):		return TransactionType.Expense
		if self.savings.match_by_tag(transaction):		return TransactionType.Savings
		return TransactionType.Unknown

	def classify_by_account(self, transaction : GenericTransaction):
		if self.income.match_by_account(transaction):	return TransactionType.Income
		if self.expense.match_by_account(transaction):	return TransactionType.Expense
		if self.savings.match_by_account(transaction):	return TransactionType.Savings
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
	config = Config("config/example.yaml")
	print(yaml.dump(config._config))
