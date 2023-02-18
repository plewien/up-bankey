import argparse
import logging as log
import yaml

from enum import Enum
from datetime import datetime
from dateutil import parser
from dateutil.relativedelta import relativedelta
from upbankapi import NotAuthorizedException

from .protocol import Client


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
	Unknown		= 'unknown'
	Ignore		= 'ignore'
	Income		= 'income'
	Expense		= 'expenses'
	Savings		= 'savings'


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
	def __init__(self, config):
		self.name = config['name']
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


class IgnoreConfig(CollectionConfig):
	def __init__(self, config):
		self.name = "Ignore"
		self.tags = ClassifierConfig(config['tags'])
		self.accounts = ClassifierConfig(config['accounts'])


class Config:
	def __init__(self):
		self.args = Config.parser().parse_args()
		config = Config._readConfig(self.args.config)
		self.since = toDateTime(config['options']['dates']['since'])
		self.until = toDateTime(config['options']['dates']['until'])
		self.limit = config['options']['sources']['up-api']['limit']
		self.pagesize = config['options']['sources']['up-api']['pagesize']
		self.ignore = IgnoreConfig(config['ignore'])
		self.collections = {TransactionType(name) : CollectionConfig(c) for name, c in config['collections'].items()}
		self.collections[TransactionType.Ignore] = IgnoreConfig(config['ignore'])

		# "Interest" will always be an income stream, so populate here
		self.collections[TransactionType.Income].accounts.add("Interest")
		self.setup()

	@staticmethod
	def parser() -> argparse.ArgumentParser:
		parser = argparse.ArgumentParser(description='Setting the config.')
		parser.add_argument('--config', type=str, default=None, help='Path to config.yaml file')
		parser.add_argument('-v', '--verbose', action="store_true", help='Verbose output')
		return parser
	
	def setup(self):
		if self.args.verbose:
			log.basicConfig(format="%(levelname)s: %(message)s", level=log.DEBUG)
			log.info("Verbose output")
		else:
			log.basicConfig(format="%(levelname)s: %(message)s")

	def __str__(self):
		return 'Dates:\n %s - %s\n' % (self.since, self.until) \
			+ 'Collections:' + '\n'.join(str(collection_config) for collection_config in self.collections.values())

	def init_client(self, constructor) -> Client:
		client : Client = constructor()
		try:
			log.info("Authorized: " + client.ping())
		except NotAuthorizedException:
			log.critical("The token is invalid")
		return client
		

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
