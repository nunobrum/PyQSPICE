from spicelib.editor.qsch_editor import QschEditor

audio_amp = QschEditor("./testfiles/AudioAmp.qsch")
print("All Components", audio_amp.get_components())
print("Capacitors", audio_amp.get_components('C'))
print("R1 info:",audio_amp.get_component_info('R1'))
print("R2 value:", audio_amp.get_component_value('R2'))
audio_amp.set_parameter('run', 1)
print(audio_amp.get_parameter('run'))
audio_amp.set_parameter('run', -1)
print(audio_amp.get_parameter('run'))
audio_amp.add_instruction('.tran 0 5m')
audio_amp.write_netlist("./testfiles/AudioAmp_rewritten.qsch")
