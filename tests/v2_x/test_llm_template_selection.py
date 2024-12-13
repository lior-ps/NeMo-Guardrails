# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from rich.logging import RichHandler

from nemoguardrails import RailsConfig
from tests.utils import TestChat

FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.DEBUG,
    format=FORMAT,
    datefmt="[%X,%f]",
    handlers=[RichHandler(markup=True)],
)

config_1 = """
colang_version: "2.x"

models:
    - type: main
      engine: openai
      model: gpt-3.5-turbo-instruct

prompts:
    - task: generate_antonym
      models:
          - openai/gpt-3.5-turbo
          - openai/gpt-4
      messages:
          - type: user
            content: |-
                Generate the antonym of the bot expression below. Use the syntax: bot say "<antonym goes here>".
          - type: user
            content: |-
                YOUR TASK:
                {{ flow_nld }}

    - task: repeat
      models:
          - openai/gpt-3.5-turbo
          - openai/gpt-4
      messages:
          - type: system
            content: |
                Your are a value generation bot that needs to generate a value for the ${{ var_name }} variable based on instructions form the user.
                Be very precised and always pick the most suitable variable type (e.g. double quotes for strings). Only generated the value and do not provide any additional response.
          - type: user
            content: |
                {{ instructions }} three times
                Assign the generated value to:
                ${{ var_name }} =

"""


def test_template_choice_in_value_generation():
    """Test template selection in value generation"""
    config = RailsConfig.from_content(
        colang_content="""
        flow main
          match UtteranceUserActionFinished(final_transcript="hi")
          $test = ..."a random bird name{{% set template = 'repeat' %}}"
          await UtteranceBotAction(script=$test)
        """,
        yaml_content=config_1,
    )

    chat = TestChat(
        config,
        llm_completions=["'parrot, raven, peacock'"],
    )

    expected_prompt = "System: Your are a value generation bot that needs to generate a value for the $test variable based on instructions form the user.\nBe very precised and always pick the most suitable variable type (e.g. double quotes for strings). Only generated the value and do not provide any additional response.\nHuman: a random bird name three times\nAssign the generated value to:\n$test ="

    chat >> "hi"
    chat << "parrot, raven, peacock"
    assert chat.llm.prompt_history[0] == expected_prompt


def test_template_choice_in_flow_generation():
    """Test template selection in flow generation"""
    config = RailsConfig.from_content(
        colang_content="""
        import core
        flow generate antonym
            \"\"\"
            {% set template = "generate_antonym" %}
            bot say "lucky"
            \"\"\"
            ...
        flow main
            match UtteranceUserActionFinished(final_transcript="hi")
            generate antonym
        """,
        yaml_content=config_1,
    )

    chat = TestChat(
        config,
        llm_completions=["bot say 'unfortunate'"],
    )

    expected_prompt = 'Human: Generate the antonym of the bot expression below. Use the syntax: bot say "<antonym goes here>".\nHuman: YOUR TASK:\n\n\nbot say "lucky"'

    chat >> "hi"
    chat << "unfortunate"
    assert chat.llm.prompt_history[0] == expected_prompt
