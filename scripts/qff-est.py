#! /usr/bin/env python

from optparse import OptionParser

from quickff.system import System
from quickff.model import Model
from quickff.program import Program
from quickff.fftable import FFTable
from quickff.paracontext import *

def parser():
    usage = "%prog [options] fns"
    description = 'This script is part of QuickFF. It calculates the harmonic'+\
                  'ff parameters a system specified in the files fns.'
    parser = OptionParser(usage=usage, description=description)
    parser.add_option(
        '--ei-model', default='Harm',
        help='Defines the potential used for the electrostatic interactions. '  +\
             'Possible choices are: Coulomb, Harmonic and Zero. Coulomb '       +\
             'implies using the coulomb potential. Harmonic implies '           +\
             'approximating the coulomb potential by means of a second order '  +\
             'Taylor expansion. Zero implies ignoring electrostatic '           +\
             'interactions. [default=%default]'
    )
    parser.add_option(
        '--ei-scales', default='1.0,1.0,1.0', type=str,
        help='Defines the scaling rule for the electrostatic interactions. '    +\
             'Three comma-separated floats are required. The first one sets '   +\
             'the scale for atoms separated by 1 bond, the second for atoms '   +\
             'separated by 2 bonds etc ... By default, all interactions are '   +\
             'left unscaled [default=%default]'
    )
    parser.add_option(
        '--ei-path', default=None,
        help='Defines the path in the HDF5 file which contains a dataset '      +\
             '`EI_PATH/charges` from which the atomic charges will be '         +\
             'extracted.'
    )
    parser.add_option(
        '--vdw-model', default='Zero',
        help='Defines the potential used for van der Waals interactions. '      +\
             'Possible choices are: LJ, Harmonic and Zero. LJ implies using '   +\
             'the Lennart-Jones potential. Harmonic implies approximating the ' +\
             'LJ potential by means of a second order Taylor expansion. Zero '  +\
             'implies ignoring electrostatic interactions. [default=%default]'
    )
    parser.add_option(
        '--vdw-scales', default='0.0,0.0,1.0', type=str,
        help='Defines the scaling rule for the van der Waals interactions. '    +\
             'Three comma-separated floats are required. The first one sets '   +\
             'the scale for atoms separated by 1 bond, the second for atoms '   +\
             'separated by 2 bonds etc ... [default=%default]'
    )
    parser.add_option(
        '--vdw-path', default=None,
        help='Defines the path in the HDF5 file which contains 2 dataset: '     +\
             '`VDW_PATH/epsilons` and `VDW_PATH/sigmas` from which the atomic ' +\
             'vdW parameters will be extracted.'
    )
    parser.add_option(
        '--vdw-from', default='none',
        help='Defines from which force field to extract vdW parameters. If '    +\
             'this value is anythin else then None, the values extracted from ' +\
             'a HDF5 file will be overwritten. Currently only UFF is supported '+\
             '[default=%default]'
    )
    parser.add_option(
        '--atypes-level', default=None,
        help='Assign atom types according to level ATYPES_LEVEL. Low will '     +\
             'assign atom types based only on atom number. Medium will assign ' +\
             'atom types based on atom number and the number of neighbors. '    +\
             'High will assign atom types based on atom number, number of '     +\
             'neighbors and the nature of the neighbors. Highest will assign '  +\
             'atom types based on atom index. None will not guess but use the ' +\
             'atom types defined in the input files fns. [default=%default]'
    )
    parser.add_option(
        '--ic-ids', default='all',
        help="A comma-separated list of identifiers specifying which icnames "  +\
             "should be included in the Valence Part. Each identifier can "     +\
             "be a specific IC name such as 'bond/C3_cc.H1_c' or can be one "   +\
             "of the following strings: 'bonds', 'angles', 'diheds', "          +\
             "'opdists' or 'all', in which case all bonds, angles, ... "        +\
             "will be included. [default=%default]"
    )
    parser.add_option(
        '--suffix', default='',
        help = "Suffix that will be added to all output files. [default='']"
    )
    parser.add_option(
        '--scoop', default=False, action='store_true',
        help = 'Use scoop distribute tasks over workers. Note that the main ' +\
               'program has to be started with -m scoop for this to work, e.g. ' +\
               'python -m scoop -n4 ~/bin/qff-est.py --scoop ...' +\
               '[default=False]'
    )
    options, fns = parser.parse_args()
    options.ei_scales = [float(x) for x in options.ei_scales.split(',')]
    options.vdw_scales = [float(x) for x in options.vdw_scales.split(',')]
    options.ic_ids = options.ic_ids.split(',')
    return fns, options

def main():
    #Parse args
    fns, options = parser()
    #Setup system, model and program
    system = System.from_files(
        fns, ei_path=options.ei_path, vdw_path=options.vdw_path
    )
    if options.atypes_level is not None:
        system.guess_ffatypes(options.atypes_level)
    if options.vdw_model.lower() != 'zero':
        if options.vdw_from.lower() == 'uff':
            system.read_uff_vdw()
        elif options.vdw_from is not 'none':
            raise ValueError('Unsupported value for vdw_from, recieved %s' %options.vdw_from)
    system.determine_ics_from_topology()
    model = Model.from_system(
        system, ic_ids=options.ic_ids,
        ei_scales=options.ei_scales, ei_pot_kind=options.ei_model,
        vdw_scales=options.vdw_scales, vdw_pot_kind=options.vdw_model,
    )
    program = Program(system, model)
    #Run program
    ff = program.run()
    #Make output
    ff.dump_ffit2('pars_ffit2%s.txt' % options.suffix, mode='w')
    ff.dump_yaff('pars_yaff%s.txt' % options.suffix, mode='w')
    if options.ei_model.lower() != 'zero':
        system.dump_charges_yaff(
            'pars_yaff%s.txt' % options.suffix,
            options.ei_scales, mode='a'
        )
    if options.vdw_model.lower() != 'zero':
        system.dump_vdw_yaff(
            'pars_yaff%s.txt' % options.suffix,
            options.vdw_scales, options.vdw_model, mode='a'
        )
    system.dump('system%s.chk' % options.suffix)

#Use scoop if requested. This has to be outside of __main__ to set the
#context for all workers
fns, options = parser()
if options.scoop:
    paracontext.use_scoop()

if __name__=='__main__':
    main()
