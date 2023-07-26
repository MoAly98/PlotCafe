
import os, re
from glob import glob
from coffea.processor import AccumulatorABC
from logger import ColoredLogger as logger

class Functor(object):
    def __init__(self, fn, args):
        self.fn = fn
        self.args = args
        assert isinstance(self.args, list)

    def evaluate(self, data):
        data_args = [data[arg] for arg in self.args]
        return self.fn(*data_args)

class Variable(object):
    def __init__(self, name, howto, binning, label, regions=['.*'], idx_by = 'event', dim = None):
        self.name = name
        self.howto = howto
        self.binning = binning
        self.label = label
        self.regions = regions
        self.idx = idx_by
        assert self.idx in ['event','nonevent']

        self.dim = dim
        assert self.dim in [1,2]

    def set_dim(self, dim):
        self.dim = dim

    def __eq__(self, other):
        return self.name == other.name

class Variables(object):
    def __init__(self, dim, tree, to_plot = []):
        if dim != 1 and dim != 2:
            print("ERROR:: Supporting only 1D and 2D variables")
            exit()
        self.dim = dim
        self.tree = tree
        for variable in to_plot:
            variable.set_dim(self.dim)

        self.to_plot = to_plot

    def append(self, variable):
        variable.set_dim(self.dim)
        self.to_plot.append(variable)

    def get_variable(self, name):
        for variable in self.to_plot:
            if variable.name == name:
                return variable
        return None

    def __iter__(self):
        for variable in self.to_plot:
            yield variable

class Sample(object):
    def __init__(self, name, stype = None, regexes = None, cut_howto = None, mc_weight = None, weight_howto = None, ignore_mcweight = None, color = None, label = None, category = None, UseAsRef = False, direcs = None):

        # Sample name
        self.name = name

        # Sample type
        assert stype.upper() in ['BKG','SIG','DATA',  '___DUMMY___'], "ERROR:: Sample type must be BKG, SIG, or DATA (case in-sensitive)"

        self.type = stype.upper()

        # Sample category
        self.category = category

        # Get files for sample
        self.regexes = regexes
        self.direcs = direcs
        self.files = []

        # Set sample cuts
        self.sel = cut_howto

        # Set sample weight
        self.weight = weight_howto
        if self.type == 'DATA':
            self.mc_weight = None
        else:
            self.mc_weight = mc_weight

        self.ignore_mcweight = ignore_mcweight
        if self.ignore_mcweight:
            self.mc_weight = None

        # Sample color
        self.color = color

        # Sample label
        self.label = label

        # Use as reference sample
        if UseAsRef:
            assert self.type != 'DATA', "ERROR:: DATA samples cannot be used as reference MC samples"

        self.ref = UseAsRef

        # Is this a super sample
        self.is_super = False


    def create_fileset(self):

        if self.regexes is None:
            return []
        # Collect Regexes
        to_glob = []
        for direc in LOOK_IN:
            to_glob.extend([f'{direc}/{regex}.root' for regex in regexes])

        # Collect files
        globbed   = []
        for wild in to_glob:
            globbed.extend(glob(wild))

        self.files = globbed
        assert self.files != [], f'NO files found for sample {self.name} with any regexes: {self.regexes}'


    def __eq__(self, other):
        return self.name == other.name

    def __str__(self):
        sample_str = f"Sample: {self.name} \n Type: {self.type} \n Category: {self.category} \n Files: {self.regexes} \n Selection: {self.sel} \n Weight: {self.weight} \n MC Weight: {self.mc_weight} \n Color: {self.color} \n Label: {self.label} \n Use as reference MC: {self.ref}"

class SuperSample(Sample):

    def __init__(self, name, subsamples = [], regexes = None, direcs = None):

        self.name = name
        self.subsamples = subsamples
        # Get files for sample
        self.regexes = regexes
        self.direcs = direcs
        self.files = []
        self.is_super = True

    def add_subsample(self, subsample):
        self.subsamples.append(subsample)

    def __len__(self):
        return len(self.subsamples)

class _DummySample(Sample):
    def __init__(self, name, stype = None, regexes = None, cut_howto = None, weight_howto = None, color = None, label = None, category = None, UseAsRef = False):
        super().__init__(name, "___DUMMY___", regexes, cut_howto, weight_howto, color, label, category, UseAsRef)


class Region(object):
    def __init__(self, name, howto, target_sample = [], label = None):
        self.name = name
        self.sel = howto
        self.targets = target_sample
        self.label = label

    def __eq__(self, other):
        return self.name == other.name


class Rescale(object):
    def __init__(self, name, affected_samples_names, howto, label = None):
        self.name   = name
        self.affects = affected_samples_names
        self.method = howto
        assert isinstance(self.method, Functor), "Rescale howto must be a functor"
        assert 'weights' in self.method.args, "A branch called weights must be in data and passed to functor for rescaling"

        self.label = label

    def __eq__(self, other):
        return self.name == other.name


class Histogram(object):

    def __init__(self, name, histo, sample, region, rescale, label = None):

        self.name   = name
        self.h = histo
        self.sample = sample
        self.region = region
        self.rescale = rescale
        self.label = label

        self.stylish_sample = None
        self.stylish_region = None
        self.stylish_rescale = None

        self.color = None

    def set_label(self, label):
        self.label = label

    def set_stylish_sample(self, sample):
        self.stylish_sample = sample

    def set_stylish_region(self, region):
        self.stylish_region = region

    def set_stylish_rescale(self, rescale):
        self.stylish_rescale = rescale

    def variances(self):
        return self.h.variances()

    def values(self):
        return self.h.values()

    def __eq__(self, other):
        return (self.name == other.name) and (self.sample == other.sample) and (self.region == other.region) and (self.rescale == other.rescale)

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            self.h *= other
        elif isinstance(other, Histogram):
            if self.name == other.name:
                self.h *= other.h
        return self

    def __rmul__(self, other):
        return self.__mul__(other)

    def __add__(self, other):
        if self.name == other.name:
            if (self.sample != other.sample and (self.sample != '___DUMMY___' and other.sample != '___DUMMY___')) or self.region != other.region or self.rescale != other.rescale:
                print("BAD!! Adding histograms", self.sample, other.sample, self.region, other.region, self.rescale, other.rescale)
            self.h += other.h
        return self


    def __radd__(self, other):
        '''
        Required for use of sum() function. This
        will add histogramsa cross sample borders
        to be used in plotting.
        '''
        if other == 0:
            return Histogram(self.name, self.h.copy(), '___DUMMY___', self.region, self.rescale)
        else:
            return self.__add__(other)

    def __repr__(self):
        return f'{self.name}__{self.sample}__{self.region}__{self.rescale}'

    def __str__(self):
            return f'Hist: {self.name}, Sample: {self.sample}, Region: {self.region}, Rescale: {self.rescale}'

class Histograms(AccumulatorABC):
    def __init__(self):
        # Initialize any necessary data structures or variables for your accumulator
        self.to_plot = {}

    def add(self, other):
        # Implement the addition logic to combine histograms
        for key, value in other.to_plot.items():
            if key in self.to_plot:
                # Add the histograms together or define your own custom logic
                self.to_plot[key] += value
            else:
                # Initialize the histogram in the accumulator if it doesn't exist
                self.to_plot[key] = value

    def __getitem__(self, histo):

        if isinstance(histo, Histogram):
            key = (histo.name, histo.sample, histo.region, histo.rescale)
        else:
            key = histo
        return self.to_plot[key]

    def identity(self):
        # Create and return a new instance of the accumulator
        return Histograms()

    def clone(self):
        # Create a copy of the accumulator
        acc = MyAccumulator()
        acc.histograms = self.to_plot.copy()
        return acc

    def __setitem__(self, histo, h ):

        if isinstance(histo, Histogram):
            key = (histo.name, histo.sample, histo.region, histo.rescale)
        else:
            key = histo
        self.to_plot[key] = h
