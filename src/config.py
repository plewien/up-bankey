import yaml
import itertools
from enum import Enum
from upbankapi.models import Transaction

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

def isInternalTransaction(transaction: Transaction):
    actions = ['Cover', 'Transfer', 'Forward', 'Quick save transfer']
    directions = ['from', 'to']
    internalDescriptions = ['%s %s ' % (a, d) for a, d in itertools.product(actions, directions)]
    internalDescriptions += ['Round Up', 'Bonus Payment']
    return transaction.description.startswith(tuple(internalDescriptions))


class TransactionType(Enum):
    Unknown     = -2
    Ignore      = -1
    Income      = 0
    Expense     = 1
    Savings     = 2


class CollectionConfig:
    def __init__(self, config):
        self.name = config['name']
        self.tags = CollectionConfig.makeSet(config['classifiers']['tags'])
        self.accounts = CollectionConfig.makeSet(config['classifiers']['accounts'])
        self.tagAliases: dict = CollectionConfig.makeAliases(config['classifiers']['tags'])
        self.accountAliases: dict = CollectionConfig.makeAliases(config['classifiers']['accounts'])

    @staticmethod
    def makeSet(l : list):
        s = set()
        for elem in l:
            if isinstance(elem, dict):
                for k in elem.keys():
                    s.add(k)
            else:
                s.add(elem)
        return s

    @staticmethod
    def makeAliases(l : list):
        listOfAliases = filter(lambda e: isinstance(e, dict), l)
        return {k:v for element in listOfAliases for (k,v) in element.items()}
        
    def getAlias(self, transaction : Transaction):
        for tag in transaction.tags:
            alias = self.tagAliases.get(tag, None)
            if alias is not None:
                return alias
    
        alias = self.accountAliases.get(transaction.description, None)
        if alias is not None:
            return alias
        
        return transaction.description

class IgnoreConfig(CollectionConfig):
    def __init__(self, config):
        self.tags = CollectionConfig.makeSet(config['tags'])
        self.accounts = CollectionConfig.makeSet(config['accounts'])

class Config:
    def __init__(self, path):
        self._config = readYaml(path)
        populateConfigRecursively(self._config, defaultConfig)
        self.ignore = IgnoreConfig(self._config['ignore'])
        self.income = CollectionConfig(self._config['collections']['income'])
        self.expense = CollectionConfig(self._config['collections']['expenses'])
        self.savings = CollectionConfig(self._config['collections']['savings'])

        self.income.accounts.add("Interest")
        yaml.dump(self._config)
            
    def filter(self, transactions):
        return filter(lambda t: not isInternalTransaction(t), transactions)

    def classify(self, transaction : Transaction):

        # TODO: Order of classification should be taken from the config
        classifierOrder = {
            self.classifyByTag, 
            self.classifyByCategoryPresence,
            self.classifyByAccount,
            self.classifyByPositiveValue,
        }
        for classifier in classifierOrder:
            classification = classifier(transaction)
            if classification is not TransactionType.Unknown:
                return classification

        return TransactionType.Unknown
        
    def classifyByTag(self, transaction : Transaction):
        tags = set(transaction.tags)
        if tags.intersection(self.ignore.tags):            return TransactionType.Ignore
        if tags.intersection(self.income.tags):            return TransactionType.Income
        if tags.intersection(self.expense.tags):           return TransactionType.Expense
        if tags.intersection(self.savings.tags):           return TransactionType.Savings
        return TransactionType.Unknown
    
    def classifyByAccount(self, transaction : Transaction):
        account = transaction.description
        if account in self.ignore.accounts:     return TransactionType.Ignore
        if account in self.income.accounts:     return TransactionType.Income
        if account in self.expense.accounts:    return TransactionType.Expense
        if account in self.savings.accounts:    return TransactionType.Savings
        return TransactionType.Unknown
    
    def classifyByCategoryPresence(self, transaction : Transaction):
        if transaction.category:
            return TransactionType.Expense
        return TransactionType.Unknown

    def classifyByPositiveValue(self, transaction : Transaction):
        if not transaction.pending and transaction.amount > 0:
            return TransactionType.Income
        return TransactionType.Unknown
        

defaultClassifier = {
    'tags': [],
    'accounts': [],
}

defaultConfig = {
    'options': {
        'path': 'results.txt',
        'expense-threshold': {
            'value': 0,
            'percentage': 0,
        }
    },
    'collections' : {
        'income': {
            'name' : 'Income',
            'classifiers' : defaultClassifier
        },
        'expenses': {
            'name' : 'Expenses',
            'classifiers' : defaultClassifier
        },
        'savings': {
            'name' : 'Savings',
            'classifiers' : defaultClassifier
        }
    },
    'ignore': defaultClassifier
    ,
}
