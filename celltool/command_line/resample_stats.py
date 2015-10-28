# Copyright 2011 Zachary Pincus
# This file is part of CellTool.
# 
# CellTool is free software; you can redistribute it and/or modify
# it under the terms of version 2 of the GNU General Public License as
# published by the Free Software Foundation.

"""Test one or more populations for statistical distinguishability.

This tool compares the distribution of a given measurement between several 
populations to determine whether the populations are distinguishable. The tool
can be run in one of two modes:
(1) All-pairs, where all input datasets are compared with one another.
(2) Reference, where other inputs are compared to a reference dataset.

In each mode, the test statistic used is the Kolmogorov-Smirnov (KS) distance
between the data for two populations. This test value is compared to a null
distribution produced by repeatedly resampling the input data and calculating
KS distances on the samples. This resampling is performed differently based on
the mode used:

In all-pairs mode, each dataset is resampled multiple times, and KS distances
calculated between pairs of resamplings of each individual dataset, giving 
(for each dataset) a null distribution of expected distances between
repeated realizations of the same dataset. Then the significance of the
distance between two different datasets is judged based on a null distribution
formed by combining the sets of KS distances calculated for both datsets 
individually.

In the reference mode, one or more reference populations can be specified. If
only one is used, then that distribution will be repeatedly resampled and the
resamplings compared against eachother (as above) to generate a single null
distribution against which the KS distance between the reference and each
non-reference distribution will be compared. If multiple reference populations
are provided (e.g. of biological replicates prepared independently), then each
reference will be compared to each other reference through multiple
resamplings, providing a null distribution of expected KS distances between
biological replicates. Then each non-reference population will be compared to
the union of all the reference populations, and the attained KS distance
compared to that null.

Input datasets are assumed to be files as generated by measure_contours or
similar. The particular measurement to be compared must be in a given data
column, which can be specified by number (the first column is numbered 1), or
if the data file has a header row, by name.

The output is a csv files of p-values that the dissimilarity between the given
datasets is due to chance alone. The columns/rows of the output are named by
the filenames of the input datasets.
"""

from celltool.utility import optparse
from celltool.utility import path
from celltool.utility import datafile
from celltool.utility import warn_tools
from celltool.utility import terminal_tools
from celltool.numerics import ks_resample
import cli_tools
import numpy


usage = "usage: %prog [options] data_column [--reference=]data_file_1 ... data_file_n"

parser = optparse.OptionParser(usage=usage, description=__doc__.strip(),
    formatter=cli_tools.CelltoolFormatter())
parser.set_defaults(
    show_progress=True,
    output_file='p_values.csv',
    n=100000,
    reference=[]
)
parser.add_option('-q', '--quiet', action='store_false', dest='show_progress',
    help='suppress progress bars and other status updates')
parser.add_option('-n', '--num-resamplings', dest='n', type='int', metavar='NUM',
    help='Number of resamplings to be performed to generate each null distribution [default: %default]')
parser.add_option('-r', '--reference', action='append',
    help='make the following data file one of the references [default: no references means all-pairs mode is used]')
parser.add_option('-o', '--output-file', metavar='FILE',
    help='CSV file to write [default: %default]')

def main(name, arguments):
    parser.prog = name
    options, args = parser.parse_args(arguments)
    args = cli_tools.glob_args(args)
    reference = cli_tools.glob_args(options.reference)
    
    if (len(args) < 2) or (len(args) + len(reference) < 3):
        raise ValueError('A data column and at least two datasets (at least one of which must not be a reference) must be provided!')
    
    data_column, datasets = args[0], args[1:]
    
    # if the data column is convertible to an integer, do so and 
    # then convert from 1-indexed to 0-indexed
    try:
        data_column = int(data_column)
        data_column -= 1
    except:
        pass

    if options.show_progress:
        datasets = terminal_tools.progress_list(datasets, "Reading input data")        
    names, pops = read_files(datasets, data_column)
    if options.show_progress and len(reference) > 0:
        reference = terminal_tools.progress_list(reference, "Reading reference data")
    ref_names, ref_pops = read_files(reference, data_column)
    
    if options.show_progress:
        pb = terminal_tools.IndeterminantProgressBar("Resampling data")
    if len(ref_pops) > 0:
        pvals = ks_resample.compare_to_ref(pops, ref_pops, options.n)
        if len(ref_names) > 1:
            ref_name = 'reference (%s)' %(', '.join(ref_names))
        else:
            ref_name = ref_names[0]
        rows = [[None, 'difference from %s'%ref_name]]
        for name, p in zip(names, pvals):
            rows.append([name, format_pval(p, options.n)])
    else: # no ref pops
        pvals = ks_resample.symmetric_comparison(pops, options.n)
        rows = [[None] + names]
        for i, (name, p_row) in enumerate(zip(names, pvals)):
            rows.append([name] + [format_pval(p, options.n) for p in p_row])
            rows[-1][i+1] = None # empty out the self-self comparison diagonal
    
    datafile.write_data_file(rows, options.output_file)    
    

def read_files(files, data_column):
    names = []
    data_out = []
    for df in files:
        names.append(path.path(df).namebase)
        data = datafile.DataFile(df, skip_empty=False, type_dict={0:str})
        header, rows = data.get_header_and_data()
        data_out.append(numpy.array([row[data_column] for row in rows]))
    return names, data_out

def format_pval(p, n):
    precision = int(numpy.ceil(numpy.log10(n)))
    smallest = 1./n
    if p < smallest:
        return '<%.*f'%(precision, smallest)
    else:
        return '%.*f'%(precision, p)

    
if __name__ == '__main__':
    import sys
    import os
    main(os.path.basename(sys.argv[0]), sys.argv[1:])


