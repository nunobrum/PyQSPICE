# QSPICE

QSPICE is a toolchain of python utilities design to interact specifically with QSPICE.

## What is contained in this repository ##

* __raw_read.py__
  A pure python class that serves to read qraw files into python.
* __spice_editor.py and qsch_editor.py__
  Scripts that can update spice netlists. The following methods are available to manipulate the component values,
  parameters as well as the simulation commands. These methods allow to update a netlist without having to open the
  schematic in Qspice. The simulations can then be run in batch mode (see sim_runner.py).

    - `set_element_model('D1', '1N4148') # Replaces the Diode D1 with the model 1N4148`
    - `set_component_value('R2', '33k') # Replaces the value of R2 by 33k`
    - `set_parameters(run=1, TEMP=80) # Creates or updates the netlist to have .PARAM run=1 or .PARAM TEMP=80`
    - `add_instructions(".STEP run -1 1023 1", ".dc V1 -5 5")`
    - `remove_instruction(".STEP run -1 1023 1")  # Removes previously added instruction`
    - `reset_netlist() # Resets all edits done to the netlist.`

* __sim_runner.py__
  A python script that can be used to run Qspice simulations in batch mode without having to open the Qspice GUI.
  This in cooperation with the classes defined in spice_editor.py or qsch_editor.py is useful because:

    - Can overcome the limitation of only stepping 3 parameters
    - Different types of simulations .TRAN .AC .NOISE can be run in a single batch
    - The RAW Files are smaller and easier to treat
    - When used with the RawRead.py and LTSteps.py, validation of the circuit can be done automatically.
    - Different models can be simulated in a single batch, by using the following instructions:

  Note: It was only tested with Windows based installations.

It is based on the [SPICELIB](https://pypi.org/project/spicelib/) library and therefore most documentation can be found there.

The major difference is that in this library all defaults point to the QSpice and the tools that are not pertaining to QSPICE are not mapped

## How to Install ##

`pip install qspice`

### Updating qspice ###

`pip install --upgrade qspice`

### Requirements ###
* spicelib


## How to use ##

Here follows a quick outlook on how to use each of the tools.

More comprehensive documentation can be found in https://spicelib.readthedocs.io/en/latest/
This is the base package on which this libray is based, however, not all functionalities 
are ported to this packages.

## LICENSE ##

GNU V3 License
(refer to the LICENSE file)

### RawRead ###

The example below reads the data from a Spice Simulation called
"TRAN - STEP.raw" and displays all steps of the "I(R1)" trace in a matplotlib plot

 ```python
from qspice import RawRead

from matplotlib import pyplot as plt

rawfile = RawRead("TRAN - STEP.raw")

print(rawfile.get_trace_names())
print(rawfile.get_raw_property())

IR1 = rawfile.get_trace("I(R1)")
x = rawfile.get_trace('time')  # Gets the time axis
steps = rawfile.get_steps()
for step in range(len(steps)):
    # print(steps[step])
    plt.plot(x.get_wave(step), IR1.get_wave(step), label=steps[step])

plt.legend()  # order a legend
plt.show()
 ```   

### SpiceEditor, QschEditor and SimRunner.py ###

This module is used to launch Qspice simulations. Results then can be processed with either the RawRead or with the
QspiceLogReader module to obtain .MEAS results.

The script will firstly invoke the Qspice in command line to generate a netlist, and then this netlist can be updated
directly by the script, in order to change component values, parameters or simulation commands.

Here follows an example of operation.

```python
from qspice import SimRunner, SpiceEditor, RawRead, sweep_log

def processing_data(raw_file, log_file):
    print("Handling the simulation data of %s, log file %s" % (raw_file, log_file))
    raw_data = RawRead(raw_file)
    vout = raw_data.get_wave('V(out)')
    return raw_file, vout.max()


# select spice model
sim = SimRunner(output_folder='./temp')
netlist = SpiceEditor('./testfiles/testfile.net')
# set default arguments
netlist.set_component_value('R1', '4k')
netlist.set_element_model('V1', "SINE(0 1 3k 0 0 0)")  # Modifying the
netlist.add_instruction(".tran 1n 3m")
netlist.add_instruction(".plot V(out)")
netlist.add_instruction(".save all")

sim_no = 1
# .step dec param cap 1p 10u 1
for cap in sweep_log(1e-12, 10e-6, 10):
    netlist.set_component_value('C1', cap)
    sim.run(netlist, callback=processing_data, run_filename=f'testfile_qspice_{sim_no}.net')
    sim_no += 1

# Reading the data
results = {}
for raw_file, vout_max in sim:  # Iterate over the results of the callback function
    results[raw_file.name] = vout_max
# The block above can be replaced by the following line
# results = {raw_file.name: vout_max for raw_file, vout_max in sim}

print(results)

# Sim Statistics
print('Successful/Total Simulations: ' + str(sim.okSim) + '/' + str(sim.runno))
input('Press Enter to delete simulation files...')
sim.file_cleanup()
```

The example above is using the SpiceEditor to create and modify a spice netlist, but it is also possible to use the
QschEditor to directly modify the .qsch file. The edited .qsch file can then be opened by the Qspice GUI and the
simulation can be run from there.

### QschEditor ###
This module is used to create and modify Qspice schematics. The following methods are available to manipulate the
component values, parameters as well as the simulation commands. These methods allow to update a schematic without
having to open the Qspice GUI. The simulations can then be run in batch mode (see sim_runner.py).

The following example shows how to read a Qspice schematic, get the information about the components, change the value
of a resistor, change the value of a parameter, add a simulation instruction and write the netlist to a file.

```python
from qspice import QschEditor

audio_amp = QschEditor("./testfiles/AudioAmp.qsch")
print("All Components", audio_amp.get_components())
print("Capacitors", audio_amp.get_components('C'))
print("R1 info:", audio_amp.get_component_info('R1'))
print("R2 value:", audio_amp.get_component_value('R2'))
audio_amp.set_parameter('run', 1)
print(audio_amp.get_parameter('run'))
audio_amp.set_parameter('run', -1)
print(audio_amp.get_parameter('run'))
audio_amp.add_instruction('.tran 0 5m')
audio_amp.save_as("./testfiles/AudioAmp_rewritten.qsch")
audio_amp.save_netlist("./testfiles/AudioAmp_rewritten.net")
```

### Simulation Analysis Toolkit ###
All the Analysis Toolkit classes are located in the spicelib.sim.toolkit package. 
The following classes are available:
  - SensitivityAnalysis
  - Montecarlo
  - WorstCaseAnalysis

Please refer to the spicelib documentation for more information.

```python
from qspice import SimRunner, QschEditor  # Imports the class that manipulates the qsch file
from spicelib.sim.tookit.montecarlo import Montecarlo  # Imports the Montecarlo toolkit class

sallenkey = QschEditor("./testfiles/AudioAmp.qsch")  # Reads the qsch file into memory
runner = SimRunner(output_folder='./temp_mc')  # Instantiates the runner with a temp folder set

mc = Montecarlo(sallenkey, runner)  # Instantiates the Montecarlo class, with the qsch file already in memory

# The following lines set the default tolerances for the components
mc.set_tolerance('R', 0.01)  # 1% tolerance, default distribution is uniform
mc.set_tolerance('C', 0.1, distribution='uniform')  # 10% tolerance, explicit uniform distribution
mc.set_tolerance('V', 0, distribution='normal')  # 10% tolerance, but using a normal distribution

# Some components can have a different tolerance
mc.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

mc.add_instruction('.func mc(x, tol) {x * (1 + tol * 2 * (random() - 0.5))}')  # Creates the missing mc() function

# Tolerances can be set for parameters as well
# mc.set_parameter_deviation('Vos', 3e-4, 5e-3, 'uniform')  # The keyword 'distribution' is optional
mc.prepare_testbench(num_runs=1000)  # Prepares the testbench for 1000 simulations
mc.editor.save_as('./testfiles/AudioAmp_mc.qsch')  # Saves the modified qsch file

# Finally the netlist is saved to a file
mc.save_netlist('./testfiles/AudioAmp_mc.net')  # TODO: Implement the conversion to spice file

mc.run(max_runs_per_sim=100)  # Runs the simulation with splits of 100 runs each
logs = mc.read_logfiles()   # Reads the log files and stores the results in the results attribute
logs.export_data('./temp_mc/data.csv')  # Exports the data to a csv file
logs.plot_histogram('fcut')  # Plots the histograms for the results
mc.cleanup_files()  # Deletes the temporary files
```

The following updates were made to the circuit:
- The value of each component was replaced by a function that generates a random value within the specified tolerance.
- The .step param run command was added to the netlist. Starts at -1 which it's the nominal value simulation, and 
finishes that the number of simulations specified in the prepare_testbench() method.
- A default value for the run parameter was added. This is useful if the .step param run is commented out.
- The R1 tolerance is different from the other resistors. This is because the tolerance was explicitly set for R1.
- The Vos parameter was added to the .param list. This is because the parameter was explicitly set using the
set_parameter_deviation method.
- Functions utol, ntol and urng were added to the .func list. These functions are used to generate random values.
Uniform distributions use the mc() function that is inspired on the approach for monte-carlo used in LTspice.

Similarly, the worst case analysis can also be setup by using the class WorstCaseAnalysis. Refer to spicelib for more
information.

### QspiceLogReader ###

This module defines a class that can be used to parse Qspice log files where the information about .STEP information is
written. There are two possible usages of this module, either programmatically by importing the module and then
accessing data through the class as exemplified here:

```python
from qspice import QspiceLogReader

data = QspiceLogReader("Batch_Test_AD820_15.log")

print("Number of steps  :", data.step_count)
step_names = data.get_step_vars()
meas_names = data.get_measure_names()

# Printing Headers
print(' '.join([f"{step:15s}" for step in step_names]), end='')  # Print steps names with no new line
print(' '.join([f"{name:15s}" for name in meas_names]), end='\n')
# Printing data
for i in range(data.step_count):
    print(' '.join([f"{data[step][i]:15}" for step in step_names]), end='')  # Print steps names with no new line
    print(' '.join([f"{data[name][i]:15}" for name in meas_names]), end='\n')  # Print Header

print("Total number of measures found :", data.measure_count)
```

## Other features (Toolkit, logging, etc..) ## 

Refer to the spicelib documentation for more information.

## To whom do I talk to? ##

* Tools website : [https://www.nunobrum.com/pyltspice.html](https://www.nunobrum.com/pyltspice.html)
* Repo owner : [me@nunobrum.com](me@nunobrum.com)
* Alternative contact : nuno.brum@gmail.com

## History ##
* Version 1.0.0
  * Alignment with spicelib 1.4.1
* Version 0.6.1
  * Alignment with spicelib 1.2.2
* Version 0.6.0
  * Hierarchical Schematics are now supported. (Alignement with spicelib 1.1.1)
* Version 0.5.1
  * Adding a tool that allows to convert LTSpice to QSpice Schematics (Alpha Stage - Not fully functional)
  * Correcting the generation of a .net from the QschEditor. (spicelib 1.0.3)
* Version 0.5.0
  * Fixes on the montecarlo example.
  * Aligning with spicelib 1.0.1
* Version 0.4
  * SimAnalysis supporting both Qspice and LTSpice logfiles.
  * FastWorstCaseAnalysis algorithm implemented
  * Fix on the log reading of fourier data.
* Version 0.3
  * Alignment with spicelib 0.8 
  * Important Bugfix on the LTComplex class.
  * Fixes and enhancing the analysis toolkit.
* Version 0.2
  * First operating version
* Version 0.1
  * Reserving library name
