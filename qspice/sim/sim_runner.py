#!/usr/bin/env python
# coding=utf-8

# -------------------------------------------------------------------------------
#
#  ███████╗██████╗ ██╗ ██████╗███████╗██╗     ██╗██████╗
#  ██╔════╝██╔══██╗██║██╔════╝██╔════╝██║     ██║██╔══██╗
#  ███████╗██████╔╝██║██║     █████╗  ██║     ██║██████╔╝
#  ╚════██║██╔═══╝ ██║██║     ██╔══╝  ██║     ██║██╔══██╗
#  ███████║██║     ██║╚██████╗███████╗███████╗██║██████╔╝
#  ╚══════╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚══════╝╚═╝╚═════╝
#
# Name:        sim_runner.py
# Purpose:     Tool used to launch LTSpice simulation in batch mode.
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Created:     23-12-2016
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""
Allows launching LTSpice simulations from a Python Script, thus allowing to overcome the 3 dimensions STEP limitation on
LTSpice, update resistor values, or component models.

The code snipped below will simulate a circuit with two different diode models, set the simulation
temperature to 80 degrees, and update the values of R1 and R2 to 3.3k. ::

    from spicelib.sim.sim_runner import SimRunner
    from spicelib.sim.sweep import sweep
    from spicelib.editor.spice_editor import SpiceEditor
    from spicelib.sim.ltspice_simulator import LTspice

    runner = SimRunner(simulator=LTspice, parallel_sims=4)
    editor = SpiceEditor("my_circuit.net")
    editor.set_parameters(temp=80)  # Sets the simulation temperature to be 80 degrees
    editor.set_component_value('R2', '3.3k')  #  Updates the resistor R2 value to be 3.3k
    for dmodel in ("BAT54", "BAT46WJ"):
        editor.set_element_model("D1", model)  # Sets the Diode D1 model
        for res_value in sweep(2.2, 2,4, 0.2):  # Steps from 2.2 to 2.4 with 0.2 increments
            editor.set_component_value('R1', res_value)  #  Updates the resistor R1 value to be 3.3k
            runner.run()

    runner.wait_completion()  # Waits for the LTSpice simulations to complete

    print("Total Simulations: {}".format(runner.runno))
    print("Successful Simulations: {}".format(runner.okSim))
    print("Failed Simulations: {}".format(runner.failSim))

The first line will create a python class instance that represents the LTSpice file or netlist that is to be
simulated. This object implements methods that are used to manipulate the spice netlist. For example, the method
set_parameters() will set or update existing parameters defined in the netlist. The method set_component_value() is
used to update existing component values or models.

---------------
Multiprocessing
---------------

For making better use of today's computer capabilities, the SimRunner spawns several simulation processes
each executing in parallel a simulation.

By default, the number of parallel simulations is 4, however the user can override this in two ways. Either
using the class constructor argument ``parallel_sims`` or by forcing the allocation of more processes in the
run() call by setting ``wait_resource=False``. ::

    `runner.run(wait_resource=False)`

The recommended way is to set the parameter ``parallel_sims`` in the class constructor. ::

    `runner = SimRunner(simulator=LTspice, parallel_sims=8)`

The user then can launch a simulation with the updates done to the netlist by calling the run() method. Since the
processes are not executed right away, but rather just scheduled for simulation, the wait_completion() function is
needed if the user wants to execute code only after the completion of all scheduled simulations.

The usage of wait_completion() is optional. Just note that the script will only end when all the scheduled tasks are
executed.

---------
Callbacks
---------

As seen above, the `wait_completion()` can be used to wait for all the simulations to be finished. However, this is
not efficient from a multiprocessor point of view. Ideally, the post-processing should be also handled while other
simulations are still running. For this purpose, the user can use a function call back.

The callback function is called when the simulation has finished directly by the thread that has handling the
simulation. A function callback receives two arguments.
The RAW file and the LOG file names. Below is an example of a callback function::

    def processing_data(raw_filename, log_filename):
        '''This is a call back function that just prints the filenames'''
        print("Simulation Raw file is %s. The log is %s" % (raw_filename, log_filename)
        # Other code below either using LTSteps.py or raw_read.py
        log_info = LTSpiceLogReader(log_filename)
        log_info.read_measures()
        rise, measures = log_info.dataset["rise_time"]

The callback function is optional. If  no callback function is given, the thread is terminated just after the
simulation is finished.
"""
__author__ = "Nuno Canto Brum <nuno.brum@gmail.com>"
__copyright__ = "Copyright 2020, Fribourg Switzerland"

__all__ = ['SimRunner']
from pathlib import Path

from spicelib.sim.sim_runner import SimRunner as SimRunnerBase
from spicelib.sim.simulator import Simulator
from ..qspice import Qspice

END_LINE_TERM = '\n'


class SimRunner(SimRunnerBase):
    """
    The SimRunner class implements all the methods required for launching batches of Spice simulations.

    :raises FileNotFoundError: When the file is not found  /!\\ This will be changed

    :param parallel_sims: Defines the number of parallel simulations that can be executed at the same time. Ideally this
                          number should be aligned to the number of CPUs (processor cores) available on the machine.
    :type parallel_sims: int, optional
    :param timeout: Timeout parameter as specified on the os subprocess.run() function. Default is 600 seconds, i.e.
        10 minutes. For no timeout, set to None.
    :type timeout: float, optional
    :param verbose: If True, it enables a richer printout of the program execution.
    :type verbose: bool, optional
    :param output_folder: specifying which directory shall be used for simulation files (raw and log files).
    :param output_folder: str

    """

    def __init__(self, *, simulator=None, parallel_sims: int = 4, timeout: float = 600.0, verbose=True,
                 output_folder: str = None):
        """Class Constructor"""
        # Gets a simulator.
        if simulator is None:
            simulator = Qspice
        elif isinstance(simulator, (str, Path)):
            simulator = Qspice.create_from(simulator)
        elif issubclass(simulator, Simulator):
            simulator = simulator
        else:
            simulator = Qspice
        super().__init__(parallel_sims=parallel_sims, timeout=timeout, verbose=verbose,
                         output_folder=output_folder, simulator=simulator)

