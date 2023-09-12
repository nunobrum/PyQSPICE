from qspice.editor.qsch_editor import QschEditor

audio_amp = QschEditor("./testfiles/AudioAmp.qsch")

audio_amp.write_netlist("./testfiles/AudioAmp_rewritten.qsch")
print(audio_amp.get_components())