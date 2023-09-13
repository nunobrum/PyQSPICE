from qspice import SimRunner, QschEditor  # Imports the class that manipulates the asc file
from spicelib.sim.tookit.worst_case import WorstCaseAnalysis

sallenkey = QschEditor("./testfiles/AudioAmp.qsch")  # Reads the asc file into memory
runner = SimRunner(output_folder='./temp_wca')  # Instantiates the runner with a temp folder set
wca = WorstCaseAnalysis(sallenkey, runner)  # Instantiates the Worst Case Analysis class

# The following lines set the default tolerances for the components
wca.set_tolerance('R', 0.01)  # 1% tolerance
wca.set_tolerance('C', 0.1)  # 10% tolerance
wca.set_tolerance('V', 0.1)  # 10% tolerance. For Worst Case analysis, the distribution is irrelevant

# Some components can have a different tolerance
wca.set_tolerance('R1', 0.05)  # 5% tolerance for R1 only. This only overrides the default tolerance for R1

# Tolerances can be set for parameters as well.
# wca.set_parameter_deviation('Vos', 3e-4, 5e-3)

# Finally the netlist is saved to a file
wca.save_netlist('./testfiles/AudioAmp_wca.qsch')

