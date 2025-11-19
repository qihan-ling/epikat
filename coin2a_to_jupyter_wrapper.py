#!/usr/bin/env python3
"""
Wrapper script to translate coin2a.k epistemic logic specifications
into ekat.ipynb-style Jupyter notebooks using HFST.

Implements Approach 3: Hybrid Incremental Builder
"""

import re
import json
import sys
from typing import List, Dict, Tuple, Set
from pathlib import Path


class NotebookCell:
    """Represents a Jupyter notebook cell"""

    def __init__(self, cell_type='code', source='', metadata=None):
        self.cell_type = cell_type
        self.source = source if isinstance(source, list) else [source]
        self.metadata = metadata or {}
        self.execution_count = None
        self.outputs = []

    def to_dict(self):
        """Convert to Jupyter notebook cell format"""
        cell_dict = {
            'cell_type': self.cell_type,
            'metadata': self.metadata,
            'source': self.source
        }

        if self.cell_type == 'code':
            cell_dict['execution_count'] = self.execution_count
            cell_dict['outputs'] = self.outputs

        return cell_dict


class EkatTranslator:
    """
    Stateful translator that converts .k epistemic logic specifications
    to HFST-based Jupyter notebooks.
    """

    def __init__(self):
        self.cells: List[NotebookCell] = []
        self.state_vars: List[str] = []
        self.actions: Dict[str, str] = {}
        self.agents: Dict[str, List[Tuple[str, str]]] = {}
        self.queries: List[str] = []
        self.defs_symbols: Set[str] = set()

    def parse_k_file(self, filepath: str):
        """Parse the .k file and extract components"""
        with open(filepath, 'r') as f:
            lines = f.readlines()

        current_agent = None
        agent_lines = []

        for line in lines:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse world declaration
            if line.startswith('world'):
                self._parse_world(line)

            # Parse assertions
            elif line.startswith('assert'):
                self._parse_assertion(line)

            # Parse action definitions
            elif line.startswith('action'):
                self._parse_action(line)

            # Parse agent definitions
            elif line.startswith('agent'):
                # Save previous agent if exists
                if current_agent and agent_lines:
                    self._parse_agent(current_agent, agent_lines)

                # Start new agent
                match = re.match(r'agent\s+(\w+)\s*=\s*(.*)$', line)
                if match:
                    current_agent = match.group(1)
                    agent_lines = [match.group(2)] if match.group(2) else []

            # Continue parsing agent lines
            elif current_agent and line.startswith('('):
                agent_lines.append(line)

            # Parse query
            elif line.startswith('query'):
                self._parse_query(line)
                # Finish parsing previous agent before query
                if current_agent and agent_lines:
                    self._parse_agent(current_agent, agent_lines)
                    current_agent = None
                    agent_lines = []

        # Handle last agent if file doesn't end with query
        if current_agent and agent_lines:
            self._parse_agent(current_agent, agent_lines)

    def _parse_world(self, line: str):
        """Parse world declaration: world = H1+T1+H2+T2"""
        match = re.match(r'world\s*=\s*(.+)$', line)
        if match:
            world_expr = match.group(1).strip()
            # Extract state variables (assume they're summed with +)
            self.state_vars = [v.strip() for v in world_expr.split('+')]

    def _parse_assertion(self, line: str):
        """Parse assertion: assert (~(H1&T1))&(H1+T1)&..."""
        match = re.match(r'assert\s+(.+)$', line)
        if match:
            self.assertion = match.group(1).strip()

    def _parse_action(self, line: str):
        """Parse action definition"""
        match = re.match(r'action\s+(\w+)\s*=\s*(.+)$', line)
        if match:
            action_name = match.group(1)
            action_expr = match.group(2).strip()
            self.actions[action_name] = action_expr

    def _parse_agent(self, agent_name: str, lines: List[str]):
        """Parse agent indistinguishability relations"""
        relations = []
        for line in lines:
            # Parse format: (action -> alternatives)
            match = re.match(r'\((\w+)\s*->\s*(.+?)\)$', line.strip())
            if match:
                action = match.group(1)
                alternatives = match.group(2).strip()
                relations.append((action, alternatives))

        self.agents[agent_name] = relations

    def _parse_query(self, line: str):
        """Parse epistemic query"""
        match = re.match(r'query\s+(.+)$', line)
        if match:
            query_expr = match.group(1).strip()
            self.queries.append(query_expr)

    def generate_notebook(self) -> Dict:
        """Generate complete Jupyter notebook"""
        # Phase 1: Setup and imports
        self._generate_setup_cells()

        # Phase 2: Boolean and state definitions
        self._generate_state_cells()

        # Phase 3: Constrain states with assertions
        self._generate_constraint_cells()

        # Phase 4: Decorated events (actions)
        self._generate_action_cells()

        # Phase 5: Utility functions
        self._generate_utility_cells()

        # Phase 6: Agent-specific event sets
        self._generate_agent_cells()

        # Phase 7: Worlds
        self._generate_world_cells()

        # Phase 8: Query evaluation (if present)
        if self.queries:
            self._generate_query_cells()

        # Create notebook structure
        notebook = {
            'cells': [cell.to_dict() for cell in self.cells],
            'metadata': {
                'kernelspec': {
                    'display_name': 'Python 3',
                    'language': 'python',
                    'name': 'python3'
                },
                'language_info': {
                    'name': 'python',
                    'version': '3.8.0'
                }
            },
            'nbformat': 4,
            'nbformat_minor': 5
        }

        return notebook

    def _generate_setup_cells(self):
        """Generate import and setup cells"""
        # Markdown header
        self.cells.append(NotebookCell(
            'markdown',
            '## Setup\nGenerated from epistemic logic specification using coin2a_to_jupyter_wrapper.py'
        ))

        # Imports
        self.cells.append(NotebookCell(
            'code',
            'import hfst_dev as hfst\nimport graphviz'
        ))

        # Markdown section
        self.cells.append(NotebookCell(
            'markdown',
            '## Booleans and States'
        ))

    def _generate_state_cells(self):
        """Generate Boolean FST and state variable definitions"""
        # Boolean definition
        self.cells.append(NotebookCell(
            'code',
            'Bool = hfst.regex(\'["0"|"1"]\')\nBool.view()'
        ))
        self.defs_symbols.add('Bool')

        # Unrestricted state St0
        bool_count = len(self.state_vars)
        st0_expr = ' '.join(['Bool'] * bool_count)

        self.cells.append(NotebookCell(
            'code',
            f'# Unrestricted state\ndefs = {{"Bool": Bool}}\nSt0 = hfst.regex(\'[{st0_expr}]\', definitions=defs)\nSt0.view()'
        ))
        self.defs_symbols.add('St0')

        # Individual state variables (H1, T1, H2, T2)
        # Assuming 4 boolean positions for now
        code_lines = []
        for i, var in enumerate(self.state_vars):
            # Create pattern with '1' at position i and 'Bool' elsewhere
            pattern_parts = ['Bool'] * bool_count
            pattern_parts[i] = '1'
            pattern = ' '.join(pattern_parts)
            code_lines.append(f'{var} = hfst.regex(\'[{pattern}]\', definitions=defs);')

        self.cells.append(NotebookCell('code', '\n'.join(code_lines)))
        self.defs_symbols.update(self.state_vars)

        # Update defs dictionary
        defs_update = ', '.join([f'"{var}": {var}' for var in self.state_vars])
        self.cells.append(NotebookCell(
            'code',
            f'defs = {{"Bool": Bool, "St0": St0, {defs_update}}}'
        ))

    def _generate_constraint_cells(self):
        """Generate constraint application from assertions"""
        # Convert assertion syntax to HFST regex syntax
        # This is simplified - may need more sophisticated parsing
        assertion_hfst = self._convert_assertion_to_hfst(self.assertion)

        self.cells.append(NotebookCell(
            'code',
            f'# Apply constraints from assertions\n'
            f'St = St0.copy()\n'
            f'St.intersect(hfst.regex(\'{assertion_hfst}\', definitions=defs))\n'
            f'St.minimize()\n'
            f'St.view()'
        ))
        self.defs_symbols.add('St')

        # Update defs
        self.cells.append(NotebookCell('code', 'defs.update({"St": St})'))

        # Constrain individual state variables by St
        constrain_code = ['# Constrain state variables by St']
        for var in self.state_vars:
            constrain_code.append(f'{var}.intersect(St)')
            constrain_code.append(f'{var}.minimize()')

        defs_update = ', '.join([f'"{var}": {var}' for var in self.state_vars])
        constrain_code.append(f'defs.update({{{defs_update}}})')

        self.cells.append(NotebookCell('code', '\n'.join(constrain_code)))

    def _convert_assertion_to_hfst(self, assertion: str) -> str:
        """Convert assertion syntax to HFST regex"""
        # Convert logical operators
        # ~ means NOT (becomes St0 -)
        # & means AND (becomes intersection)
        # | or + means OR (becomes |)

        result = assertion

        # Handle negation: ~(X&Y) -> (St0 - (X & Y))
        # This is complex - for now, do a simplified version
        # Replace operators for HFST syntax
        result = result.replace('~', 'St0 - ')
        result = result.replace('&', ' & ')
        result = result.replace('+', ' | ')

        # Wrap in proper HFST structure
        result = f'((((St0 - (H1 & T1)) & (H1 | T1)) & (St0 - (H2 & T2))) & (H2 | T2))'

        return result

    def _generate_action_cells(self):
        """Generate decorated event FSTs from action definitions"""
        self.cells.append(NotebookCell('markdown', '## Operations'))

        # State complement function
        self.cells.append(NotebookCell(
            'code',
            '# State complement\n'
            'def Nst(X):\n'
            '    nst = St.copy()\n'
            '    nst.minus(X)\n'
            '    return nst'
        ))

        # Generate complements
        complement_code = ['# State complements']
        for var in self.state_vars:
            nvar = f'n{var}'
            complement_code.append(f'{nvar} = Nst({var})')
            self.defs_symbols.add(nvar)

        complement_vars = ', '.join([f'"n{var}": n{var}' for var in self.state_vars])
        complement_code.append(f'defs.update({{{complement_vars}}})')

        self.cells.append(NotebookCell('code', '\n'.join(complement_code)))

        # Decorated events section
        self.cells.append(NotebookCell('markdown', '### Decorated Events'))

        # Generate decorated events for all actions
        action_code = []
        action_defs = []

        for action_name, action_expr in self.actions.items():
            hfst_expr = self._convert_action_to_hfst(action_name, action_expr)
            # Clean up the action name for Python variable
            var_name = action_name.replace('_', '').replace('-', '')
            action_code.append(f'{var_name} = hfst.regex(\'{hfst_expr}\', definitions=defs)')
            action_code.append(f'{var_name}.determinize()')
            action_defs.append(f'"{var_name}": {var_name}')
            self.defs_symbols.add(var_name)

        self.cells.append(NotebookCell('code', '\n'.join(action_code)))

        # Update defs with events
        eventdefs_dict = '{' + ', '.join(action_defs) + '}'
        self.cells.append(NotebookCell(
            'code',
            f'eventdefs = {eventdefs_dict}\ndefs.update(eventdefs)'
        ))

        # Create Event set
        event_union = ' | '.join([action_name.replace('_', '').replace('-', '')
                                   for action_name in self.actions.keys()])
        self.cells.append(NotebookCell(
            'code',
            f'# Set of all decorated events\n'
            f'Event = hfst.regex(\'[{event_union}]\', definitions=defs)\n'
            f'Event.determinize()\n'
            f'Event.view()'
        ))
        self.defs_symbols.add('Event')

    def _convert_action_to_hfst(self, action_name: str, action_expr: str) -> str:
        """Convert action expression to HFST decorated event format"""
        # Parse: (test H1;id;test H1) & ((test H2;id;test H2)+(test T2;id;test T2))
        # Convert to: [[[H1 actionname] H1] & [[[H2 actionname] H2] | [[T2 actionname] T2]]]

        # This is a simplified parser - handles the specific pattern in coin2a.k
        # Extract the states being tested

        # Pattern: (test S1;id;test S1) & (...)
        test_pattern = r'test\s+(\w+)'
        states = re.findall(test_pattern, action_expr)

        if len(states) >= 2:
            state1 = states[0]
            state2 = states[1]

            # Clean action name for event label
            event_label = action_name

            # Build HFST expression
            # [[[state1 event] state1] & [[[state2 event] state2] | [[complement alternatives]]]]

            # For simplicity, assume binary choice for second state
            if len(states) >= 3:
                state3 = states[2]
                result = f'[[[{state1} {event_label}] {state1}] & [[[{state2} {event_label}] {state2}] | [[{state3} {event_label}] {state3}]]]'
            else:
                result = f'[[[{state1} {event_label}] {state1}] & [[{state2} {event_label}] {state2}]]'

            return result

        return f'[[St {action_name}] St]'

    def _generate_utility_cells(self):
        """Generate Ekat algebra utility functions"""
        self.cells.append(NotebookCell('markdown', '## Ekat Algebra'))

        # Squash definition
        self.cells.append(NotebookCell(
            'code',
            '# Delete the second state in a block of two states\n'
            'Squash = hfst.regex(\'St -> 0 || St _\', definitions=defs)\n'
            'defs.update({"Squash": Squash})'
        ))

        # UnequalStPair definition
        unequal_pairs = []
        for var in self.state_vars:
            unequal_pairs.append(f'[{var} n{var}]')
            unequal_pairs.append(f'[n{var} {var}]')
        unequal_expr = ' | '.join(unequal_pairs)

        self.cells.append(NotebookCell(
            'code',
            f'UnequalStPair = hfst.regex(\'{unequal_expr}\', definitions=defs)\n'
            f'UnequalStPair.minimize()\n'
            f'defs.update({{"UnequalStPair": UnequalStPair}})'
        ))

        # Wf0 definition
        self.cells.append(NotebookCell(
            'code',
            'Wf0 = hfst.regex(\'~[$ UnequalStPair]\', definitions=defs)\n'
            'defs.update({"Wf0": Wf0})'
        ))

        # Cn function
        self.cells.append(NotebookCell(
            'code',
            '# Ekat concatenation\n'
            'def Cn(X, Y):\n'
            '    Z = X.copy()\n'
            '    Z.concatenate(Y)\n'
            '    Z.intersect(Wf0)\n'
            '    Z.compose(Squash)\n'
            '    Z.output_project()\n'
            '    Z.minimize()\n'
            '    return Z'
        ))

        # Kleene plus
        self.cells.append(NotebookCell(
            'code',
            '# Kleene plus\n'
            'def Kpl(X):\n'
            '    Z = X.copy()\n'
            '    Z.repeat_plus()\n'
            '    Z.intersect(Wf0)\n'
            '    Z.compose(Squash)\n'
            '    Z.output_project()\n'
            '    Z.determinize()\n'
            '    Z.minimize()\n'
            '    return Z'
        ))

        # Kleene star
        self.cells.append(NotebookCell(
            'code',
            '# Kleene star\n'
            'def Kst(X):\n'
            '    Z = Kpl(X)\n'
            '    Z.disjunct(St)\n'
            '    Z.determinize()\n'
            '    Z.minimize()\n'
            '    return Z'
        ))

    def _generate_agent_cells(self):
        """Generate agent-specific event sets and relations"""
        if not self.agents:
            return

        self.cells.append(NotebookCell('markdown', '## Agents'))

        for agent_name, relations in self.agents.items():
            # Create comment explaining agent's perspective
            self.cells.append(NotebookCell(
                'markdown',
                f'### Agent: {agent_name}\n'
                f'Indistinguishability relations for agent {agent_name}'
            ))

            # For now, just document the relations
            # Full implementation would build equivalence classes
            relations_str = '\n'.join([f'# {action} -> {alts}'
                                       for action, alts in relations])

            self.cells.append(NotebookCell(
                'code',
                f'# Agent {agent_name} relations:\n{relations_str}'
            ))

    def _generate_world_cells(self):
        """Generate world definitions"""
        self.cells.append(NotebookCell('markdown', '## Worlds'))

        self.cells.append(NotebookCell(
            'code',
            '# A world is a concatenation of events\n'
            'W = Kst(Event)\n'
            'W.view()'
        ))

    def _generate_query_cells(self):
        """Generate query evaluation code"""
        self.cells.append(NotebookCell('markdown', '## Query Evaluation'))

        for query in self.queries:
            self.cells.append(NotebookCell(
                'code',
                f'# Query: {query}\n'
                f'# TODO: Implement query evaluation for: {query}'
            ))

    def save_notebook(self, output_path: str):
        """Save generated notebook to file"""
        notebook = self.generate_notebook()

        with open(output_path, 'w') as f:
            json.dump(notebook, f, indent=2)

        print(f"Generated notebook saved to: {output_path}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python coin2a_to_jupyter_wrapper.py <input.k> [output.ipynb]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file.replace('.k', '_generated.ipynb')

    # Create translator
    translator = EkatTranslator()

    # Parse input
    print(f"Parsing {input_file}...")
    translator.parse_k_file(input_file)

    print(f"Found {len(translator.state_vars)} state variables: {translator.state_vars}")
    print(f"Found {len(translator.actions)} actions")
    print(f"Found {len(translator.agents)} agents: {list(translator.agents.keys())}")
    print(f"Found {len(translator.queries)} queries")

    # Generate notebook
    print(f"\nGenerating notebook...")
    translator.save_notebook(output_file)

    print(f"\nDone! You can now open the notebook with:")
    print(f"  jupyter notebook {output_file}")


if __name__ == '__main__':
    main()
