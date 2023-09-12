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
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from langchain.llms.base import LLM
from pydantic import BaseModel

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.colang.v1_1.runtime.flows import FlowConfig
from nemoguardrails.utils import new_event_dict


class FakeLLM(LLM, BaseModel):
    """Fake LLM wrapper for testing purposes."""

    responses: List
    i: int = 0

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "fake-list"

    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """First try to lookup in queries, else return 'foo' or 'bar'."""
        response = self.responses[self.i]
        self.i += 1
        return response

    async def _acall(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        """First try to lookup in queries, else return 'foo' or 'bar'."""
        response = self.responses[self.i]
        self.i += 1
        return response

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        return {}


class TestChat:
    """Helper class for easily writing tests.

    Usage:
        config = RailsConfig.from_path(...)
        chat = TestChat(
            config,
            llm_completions=[
                "Hello! How can I help you today?",
            ],
        )

        chat.user("Hello! How are you?")
        chat.bot("Hello! How can I help you today?")

    """

    # Tell pytest that this class is not meant to hold tests.
    __test__ = False

    def __init__(self, config: RailsConfig, llm_completions: List[str]):
        """Creates a TestChat instance.

        :param config: The rails configuration that should be used.
        :param llm_completions: The completions that should be generated by the fake LLM.
        """
        self.llm = FakeLLM(responses=llm_completions)
        self.config = config
        self.app = LLMRails(config, llm=self.llm)

        # Track the conversation for v1.0
        self.history = []

        # Track the conversation for v1.1
        self.input_events = []
        self.state = None

        # For 1.1, we start the main flow when initializing by providing a empty state
        if self.config.colang_version == "1.1":
            _, self.state = self.app.process_events(
                [],
                self.state,
            )

    def user(self, msg: str):
        if self.config.colang_version == "1.0":
            self.history.append({"role": "user", "content": msg})
        elif self.config.colang_version == "1.1":
            self.input_events.append(
                {
                    "type": "UtteranceUserActionFinished",
                    "final_transcript": msg,
                }
            )
        else:
            raise Exception(f"Invalid colang version: {self.config.colang_version}")

    def bot(self, msg: str):
        if self.config.colang_version == "1.0":
            result = self.app.generate(messages=self.history)
            assert result, "Did not receive any result"
            assert (
                result["content"] == msg
            ), f"Expected `{msg}` and received `{result['content']}`"
            self.history.append(result)

        elif self.config.colang_version == "1.1":
            output_msgs = []
            while self.input_events:
                output_events, output_state = self.app.process_events(
                    self.input_events, self.state
                )

                # We detect any "StartUtteranceBotAction" events, show the message, and
                # generate the corresponding Finished events as new input events.
                self.input_events = []
                for event in output_events:
                    if event["type"] == "StartUtteranceBotAction":
                        output_msgs.append(event["script"])

                        self.input_events.append(
                            new_event_dict(
                                "UtteranceBotActionFinished",
                                action_uid=event["action_uid"],
                                is_success=True,
                                final_script=event["script"],
                            )
                        )

                self.state = output_state

            output_msg = "\n".join(output_msgs)
            assert output_msg == msg, f"Expected `{msg}` and received `{output_msg}`"
        else:
            raise Exception(f"Invalid colang version: {self.config.colang_version}")

    def __rshift__(self, msg: str):
        self.user(msg)

    def __lshift__(self, msg: str):
        self.bot(msg)


def clean_events(events: List[dict]):
    """Removes private context parameters (starting with '_') from a list of events
    generated by the runtime for a test case.

    If the context update event will be empty after removing all private context parameters,
    the entire event is removed from the list.

    :param events: The list of events generated by the runtime for a test case.
    """
    for e in events:
        if e["type"] == "ContextUpdate":
            for key in list(e["data"].keys()):
                if key.startswith("_"):
                    del e["data"][key]
    for e in events[:]:
        if e["type"] == "ContextUpdate" and len(e["data"]) == 0:
            events.remove(e)


def event_conforms(event_subset: Dict[str, Any], event_to_test: Dict[str, Any]) -> bool:
    """Tests if the `event_to_test` conforms to the event_subset. Conforming means that for all key,value paris in `event_subset` the value has to match."""
    for key, value in event_subset.items():
        if key not in event_to_test:
            return False

        if isinstance(value, dict) and isinstance(event_to_test[key], dict):
            if not event_conforms(value, event_to_test[key]):
                return False
        elif isinstance(value, list) and isinstance(event_to_test[key], list):
            return all(
                [event_conforms(s, e) for s, e in zip(value, event_to_test[key])]
            )
        elif value != event_to_test[key]:
            return False

    return True


def event_sequence_conforms(
    event_subset_list: Iterable[Dict[str, Any]], event_list: Iterable[Dict[str, Any]]
) -> bool:
    if len(event_subset_list) != len(event_list):
        return False

    for subset, event in zip(event_subset_list, event_list):
        if not event_conforms(subset, event):
            return False

    return True


def any_event_conforms(
    event_subset: Dict[str, Any], event_list: Iterable[Dict[str, Any]]
) -> bool:
    """Returns true iff one of the events in the list conform to the event_subset provided."""
    return any([event_conforms(event_subset, e) for e in event_list])


def is_data_in_events(
    events: List[Dict[str, Any]], event_data: List[Dict[str, Any]]
) -> bool:
    """Returns 'True' if provided data is contained in event."""
    if len(events) != len(event_data):
        return False

    for event, data in zip(events, event_data):
        if not (
            all(key in event for key in data)
            and all(data[key] == event[key] for key in data)
        ):
            return False
    return True


def convert_parsed_colang_to_flow_config(
    parsed_colang: Dict[str, Any]
) -> Dict[str, FlowConfig]:
    """Converts the parsed colang to a flow configuration."""
    return dict(
        [
            (
                flow["name"],
                FlowConfig(
                    id=flow["name"],
                    loop_id=None,
                    elements=flow["elements"],
                    parameters=flow["parameters"],
                ),
            )
            for flow in parsed_colang["flows"]
        ]
    )
