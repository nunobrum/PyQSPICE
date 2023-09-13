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
# Name:        qsch_editor.py
# Purpose:     Class made to update directly the QSPICE Schematic files
#
# Author:      Nuno Brum (nuno.brum@gmail.com)
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
from pathlib import Path
from typing import Union, Tuple, List
import re
import logging
from spicelib.editor.base_editor import (
    BaseEditor, format_eng, ComponentNotFoundError, ParameterNotFoundError,
    PARAM_REGEX, UNIQUE_SIMULATION_DOT_INSTRUCTIONS
)
__all__ = ('QschEditor', )

_logger = logging.getLogger("qspice.QschEditor")

QSCH_HEADER = (255, 216, 255, 219)
QSCH_TEXT_POS = 1
QSCH_TEXT_STR_ATTR = 8
QSCH_COMPONENT_POS = 1
QSCH_SYMBOL_TEXT_REFDES = 0
QSCH_SYMBOL_TEXT_VALUE = 1


class QschReadingError(IOError):
    ...


class QschTag:
    def __init__(self, stream, start):
        assert stream[start] == '«'
        self.start = start
        self.items = []
        self.tokens = []
        i = start + 1
        i0 = i
        while i < len(stream):
            if stream[i] == '«':
                child = QschTag(stream, i)
                i = child.stop
                i0 = i + 1
                self.items.append(child)
            elif stream[i] == '»':
                self.stop = i + 1
                if i > i0:
                    self.tokens.append(stream[i0:i])
                break
            elif stream[i] == ' ' or stream[i] == '\n':
                if i > i0:
                    self.tokens.append(stream[i0:i])
                i0 = i + 1
            elif stream[i] == '"':
                # get all characters until the next " sign
                i += 1
                while stream[i] != '"':
                    i += 1
            elif stream[i] == '(':
                # todo: handle nested parenthesis and also [] and {}
                i += 1
                while stream[i] != ')':
                    i += 1
            i += 1
        else:
            raise IOError("Missing » when reading file")

    def __str__(self):
        """Returns only the first line"""
        return ' '.join(self.tokens)

    def out(self, level):
        spaces = '  ' * level
        if len(self.items):
            return (f"{spaces}«{' '.join(self.tokens)}\n"
                    f"{''.join(tag.out(level+1) for tag in self.items)}"
                    f"{spaces}»\n")
        else:
            return f"{'  ' * level}«{' '.join(self.tokens)}»\n"

    @property
    def tag(self) -> str:
        return self.tokens[0]

    def get_items(self, item) -> List['QschTag']:
        answer = [tag for tag in self.items if tag.tag == item]
        return answer

    def get_attr(self, index: int):
        a = self.tokens[index]
        if a.startswith('(') and a.endswith(')'):
            return tuple(int(x) for x in a[1:-1].split(','))
        elif a.startswith('0x'):
            return int(a[2:], 16)
        elif a.startswith('"') and a.endswith('"'):
            return a[1:-1]
        else:
            return int(a)

    def set_attr(self, index: int, value):
        if isinstance(value, int):
            value_str = str(value)
        elif isinstance(value, str):
            if value.startswith('0x'):
                value_str = value
            else:
                value_str = f'"{value}"'
        else:
            raise ValueError("Object not supported in set_attr")
        self.tokens[index] = value_str

    def get_text(self, label) -> str:
        a = self.get_items(label+':')
        if len(a) != 1:
            raise IndexError(f"Label {label}: not found")
        return a[0].tokens[1]


class QschEditor(BaseEditor):
    """Class made to update directly the LTspice ASC files"""

    def __init__(self, asc_file: str):
        self._qsch_file_path = Path(asc_file)
        self.schematic = None
        self._symbols = {}
        if not self._qsch_file_path.exists():
            raise FileNotFoundError(f"File {asc_file} not found")
        # read the file into memory
        self.reset_netlist()

    @property
    def circuit_file(self) -> Path:
        return self._qsch_file_path

    def write_netlist(self, run_netlist_file: Union[str, Path]) -> None:
        if isinstance(run_netlist_file, str):
            run_netlist_file = Path(run_netlist_file)
        run_netlist_file = run_netlist_file.with_suffix(".qsch")
        if self.schematic is None:
            _logger.error("Empty Schematic information")
            return
        with open(run_netlist_file, 'w') as qsch_file:
            _logger.info(f"Writing ASC file {run_netlist_file}")
            for c in QSCH_HEADER:
                qsch_file.write(chr(c))
            qsch_file.write(self.schematic.out(0))
            qsch_file.write('\n')  # Terminates the new line

    def reset_netlist(self):
        with open(self._qsch_file_path, 'r') as asc_file:
            _logger.info(f"Reading QSCH file {self._qsch_file_path}")
            stream = asc_file.read()
        self._parse_qsch_stream(stream)

    def _parse_qsch_stream(self, stream):

        self._symbols.clear()
        _logger.debug("Parsing ASC file")
        header = tuple(ord(c) for c in stream[:4])

        if header != QSCH_HEADER:
            raise QschReadingError("Missing header. The QSCH file should start with: " +
                                   f"{' '.join(f'{c:02X}' for c in QSCH_HEADER)}")

        schematic = QschTag(stream, 4)
        self.schematic = schematic

        components = self.schematic.get_items('component')
        for component in components:
            symbol: QschTag = component.get_items('symbol')[0]
            typ = symbol.get_text('type')
            desc = symbol.get_text('description')
            texts = symbol.get_items('text')
            if len(texts) < 2:
                raise RuntimeError(f"Missing texts in component at coordinates {component.get_attr(1)}")
            refdes = texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR)
            value = texts[QSCH_SYMBOL_TEXT_VALUE].get_attr(QSCH_TEXT_STR_ATTR)
            self._symbols[refdes] = {
                'type': typ,
                'description': desc,
                'model': value,
                'tag': component
            }

    def get_component_info(self, component) -> dict:
        """Returns the component information as a dictionary"""
        if component not in self._symbols:
            _logger.error(f"Component {component} not found in ASC file")
            raise ComponentNotFoundError(f"Component {component} not found in ASC file")
        return self._symbols[component]

    def _get_text_matching(self, command, search_expression: re.Pattern):
        command_upped = command.upper()
        text_tags = self.schematic.get_items('text')
        for tag in text_tags:
            line = tag.get_attr(QSCH_TEXT_STR_ATTR)
            if line.upper().startswith(command_upped):
                match = search_expression.search(line)
                if match:
                    return tag, match
        else:
            return None, None

    def get_parameter(self, param: str) -> str:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            return match.group('value')
        else:
            raise ParameterNotFoundError(f"Parameter {param} not found in ASC file")

    def set_parameter(self, param: str, value: Union[str, int, float]) -> None:
        param_regex = re.compile(PARAM_REGEX % param, re.IGNORECASE)
        tag, match = self._get_text_matching(".PARAM", param_regex)
        if match:
            _logger.debug(f"Parameter {param} found in ASC file, updating it")
            if isinstance(value, (int, float)):
                value_str = format_eng(value)
            else:
                value_str = value
            text: str = tag.get_attr(QSCH_TEXT_STR_ATTR)
            match = param_regex.search(text)  # repeating the search, so we update the correct start/stop parameter
            start, stop = match.span(param_regex.groupindex['replace'])
            text =  text[:start] + "{}={}".format(param, value_str) + text[stop:]
            tag.set_attr(QSCH_TEXT_STR_ATTR, text)
            _logger.info(f"Parameter {param} updated to {value_str}")
            _logger.debug(f"Text at {tag.get_attr(QSCH_TEXT_POS)} Updated to {text}")
        else:
            # Was not found so we need to add it,
            _logger.debug(f"Parameter {param} not found in ASC file, adding it")
            x, y = self._get_text_space()
            tag = QschTag(f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 ".param {param}={value}"»', 0)
            self.schematic.items.append(tag)
            _logger.info(f"Parameter {param} added with value {value}")
            _logger.debug(f"Text added to {tag.get_attr(QSCH_TEXT_POS)} Added: {tag.get_attr(QSCH_TEXT_STR_ATTR)}")

    def set_component_value(self, device: str, value: Union[str, int, float]) -> None:
        if isinstance(value, str):
            value_str = value
        else:
            value_str = format_eng(value)
        self.set_element_model(device, value_str)

    def set_element_model(self, device: str, model: str) -> None:
        comp_info = self.get_component_info(device)
        component: QschTag = comp_info['tag']
        symbol: QschTag = component.get_items('symbol')[0]
        texts = symbol.get_items('text')
        assert texts[QSCH_SYMBOL_TEXT_REFDES].get_attr(QSCH_TEXT_STR_ATTR) == device
        texts[QSCH_SYMBOL_TEXT_VALUE].set_attr(QSCH_TEXT_STR_ATTR, model)
        _logger.info(f"Component {device} updated to {model}")
        _logger.debug(f"Component at :{component.get_attr(1)} Updated")

    def get_component_value(self, element: str) -> str:
        comp_info = self.get_component_info(element)
        if "model" not in comp_info:
            _logger.error(f"Component {element} does not have a Value attribute")
            raise ComponentNotFoundError(f"Component {element} does not have a Value attribute")
        return comp_info["model"]

    def get_components(self, prefixes='*') -> list:
        if prefixes == '*':
            return list(self._symbols.keys())
        return [k for k in self._symbols.keys() if k[0] in prefixes]

    def remove_component(self, designator: str):
        comp_info = self.get_component_info(designator)
        component: QschTag = comp_info['tag']
        self.schematic.items.remove(component)

    def _get_text_space(self):
        """
        Returns the coordinate on the Schematic File canvas where a text can be appended.
        """
        min_x = 100000   # High enough to be sure it will be replaced
        max_x = -100000  # Low enough to be sure it will be replaced
        min_y = 100000   # High enough to be sure it will be replaced
        max_y = -100000  # Low enough to be sure it will be replaced
        for tag in self.schematic.items:
            if tag.tag == 'component':
                x1, y1 = tag.get_attr(1)
                x2, y2 = x1, y1  # todo: the whole component primitives
            elif tag.tag == 'wire':
                x1, y1 = tag.get_attr(1)
                x2, y2 = tag.get_attr(2)
            elif tag.tag == 'net':
                x1, y1 = tag.get_attr(1)
                x2, y2 = x1, y1

            min_x = min(min_x, x1, x2)
            max_x = max(max_x, x1, x2)
            min_y = min(min_y, y1, y2)
            max_y = max(max_y, y1, y2)

        return min_x, min_y - 24  # Setting the text in the bottom left corner of the canvas

    def add_instruction(self, instruction: str) -> None:
        instruction = instruction.strip()  # Clean any end of line terminators
        command = instruction.split()[0].upper()

        if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
            # Before adding new instruction, if it is a unique instruction, we just replace it
            for text_tag in self.schematic.get_items('text'):
                text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
                command = text.split()[0].upper()
                if command in UNIQUE_SIMULATION_DOT_INSTRUCTIONS:
                    text_tag.set_attr(QSCH_TEXT_STR_ATTR, instruction)
                    return  # Job done, can exit this method

        elif command.startswith('.PARAM'):
            raise RuntimeError('The .PARAM instruction should be added using the "set_parameter" method')
        # If we get here, then the instruction was not found, so we need to add it
        x, y = self._get_text_space()
        tag = QschTag(f'«text ({x},{y}) 1 0 0 0x1000000 -1 -1 "{instruction}"»', 0)
        self.schematic.items(tag)

    def remove_instruction(self, instruction: str) -> None:
        for text_tag in self.schematic.get_items('text'):
            text = text_tag.get_attr(QSCH_TEXT_STR_ATTR)
            if instruction in text_tag:
                self.schematic.items.remove(text_tag)
                return  # Job done, can exit this method

        msg = f'Instruction "{instruction}" not found'
        _logger.error(msg)
        raise RuntimeError(msg)
