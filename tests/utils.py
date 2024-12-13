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

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from langchain.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.llms import LLM
from pydantic import Field

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.colang import parse_colang_file
from nemoguardrails.colang.v2_x.runtime.flows import State
from nemoguardrails.colang.v2_x.runtime.runtime import (
    create_flow_configs_from_flow_list,
)
from nemoguardrails.colang.v2_x.runtime.statemachine import initialize_state
from nemoguardrails.utils import EnhancedJsonEncoder, new_event_dict, new_uuid


class FakeLLM(LLM):
    """Fake LLM wrapper for testing purposes."""

    responses: List
    prompt_history: List[str] = Field(default_factory=list, exclude=True)
    i: int = 0
    streaming: bool = False

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "fake-list"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if self.i >= len(self.responses):
            raise RuntimeError(
                f"No responses available for query number {self.i + 1} in FakeLLM. "
                "Most likely, too many LLM calls are made or additional responses need to be provided."
            )
        self.prompt_history.append(prompt)
        response = self.responses[self.i]
        self.i += 1
        return response

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if self.i >= len(self.responses):
            raise RuntimeError(
                f"No responses available for query number {self.i + 1} in FakeLLM. "
                "Most likely, too many LLM calls are made or additional responses need to be provided."
            )
        self.prompt_history.append(prompt)
        response = self.responses[self.i]
        self.i += 1

        if self.streaming and run_manager:
            # To mock streaming, we just split in chunk by spaces
            chunks = response.split(" ")
            for i in range(len(chunks)):
                if i < len(chunks) - 1:
                    chunk = chunks[i] + " "
                else:
                    chunk = chunks[i]

                await asyncio.sleep(0.05)
                await run_manager.on_llm_new_token(token=chunk, chunk=chunk)

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

    def __init__(
        self,
        config: RailsConfig,
        llm_completions: Optional[List[str]] = None,
        streaming: bool = False,
    ):
        """Creates a TestChat instance.

        If a set of LLM completions are specified, a FakeLLM instance will be used.

        Args
            config: The rails configuration that should be used.
            llm_completions: The completions that should be generated by the fake LLM.
        """
        self.llm = (
            FakeLLM(responses=llm_completions, streaming=streaming)
            if llm_completions is not None
            else None
        )
        self.config = config
        self.app = LLMRails(config, llm=self.llm)

        # Track the conversation for v1.0
        self.history = []
        self.streaming = streaming

        # Track the conversation for v2.x
        self.input_events = []
        self.state = None

        # For 2.x, we start the main flow when initializing by providing a empty state
        if self.config.colang_version == "2.x":
            self.app.runtime.disable_async_execution = True
            _, self.state = self.app.process_events(
                [],
                self.state,
            )

    def user(self, msg: Union[str, dict]):
        if self.config.colang_version == "1.0":
            self.history.append({"role": "user", "content": msg})
        elif self.config.colang_version == "2.x":
            if isinstance(msg, str):
                uid = new_uuid()
                self.input_events.extend(
                    [
                        new_event_dict("UtteranceUserActionStarted", action_uid=uid),
                        new_event_dict(
                            "UtteranceUserActionFinished",
                            final_transcript=msg,
                            action_uid=uid,
                            is_success=True,
                            event_created_at=(
                                datetime.now(timezone.utc) + timedelta(milliseconds=1)
                            ).isoformat(),
                            action_finished_at=(
                                datetime.now(timezone.utc) + timedelta(milliseconds=1)
                            ).isoformat(),
                        ),
                    ]
                )
            elif "type" in msg:
                self.input_events.append(msg)
            else:
                raise ValueError(
                    f"Invalid user message: {msg}. Must be either str or event"
                )
        else:
            raise Exception(f"Invalid colang version: {self.config.colang_version}")

    def bot(self, expected: Union[str, dict, list[dict]]):
        if self.config.colang_version == "1.0":
            result = self.app.generate(messages=self.history)
            assert result, "Did not receive any result"
            assert (
                result["content"] == expected
            ), f"Expected `{expected}` and received `{result['content']}`"
            self.history.append(result)

        elif self.config.colang_version == "2.x":
            output_msgs = []
            output_events = []
            while self.input_events:
                event = self.input_events.pop(0)
                out_events, output_state = self.app.process_events([event], self.state)
                output_events.extend(out_events)

                # We detect any "StartUtteranceBotAction" events, show the message, and
                # generate the corresponding Finished events as new input events.
                for event in out_events:
                    if event["type"] == "StartUtteranceBotAction":
                        output_msgs.append(event["script"])
                        self.input_events.append(
                            new_event_dict(
                                "UtteranceBotActionStarted",
                                action_uid=event["action_uid"],
                            )
                        )
                        self.input_events.append(
                            new_event_dict(
                                "UtteranceBotActionStarted",
                                action_uid=event["action_uid"],
                            )
                        )
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
            if isinstance(expected, str):
                assert (
                    output_msg == expected
                ), f"Expected `{expected}` and received `{output_msg}`"
            else:
                if isinstance(expected, dict):
                    expected = [expected]
                assert is_data_in_events(output_events, expected)

        else:
            raise Exception(f"Invalid colang version: {self.config.colang_version}")

    async def bot_async(self, msg: str):
        result = await self.app.generate_async(messages=self.history)
        assert result, "Did not receive any result"
        assert (
            result["content"] == msg
        ), f"Expected `{msg}` and received `{result['content']}`"
        self.history.append(result)

    def __rshift__(self, msg: Union[str, dict]):
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
        raise Exception(
            f"Different lengths: {len(event_subset_list)} vs {len(event_list)}"
        )

    for subset, event in zip(event_subset_list, event_list):
        if not event_conforms(subset, event):
            raise Exception(f"Mismatch: {subset} vs {event}")

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


def _init_state(colang_content, yaml_content: Optional[str] = None) -> State:
    config = create_flow_configs_from_flow_list(
        parse_colang_file(
            filename="",
            content=colang_content,
            include_source_mapping=True,
            version="2.x",
        )["flows"]
    )

    rails_config = None
    if yaml_content:
        rails_config = RailsConfig.from_content(colang_content, yaml_content)
    json.dump(config, sys.stdout, indent=4, cls=EnhancedJsonEncoder)
    state = State(flow_states=[], flow_configs=config, rails_config=rails_config)
    initialize_state(state)
    print("---------------------------------")
    json.dump(state.flow_configs, sys.stdout, indent=4, cls=EnhancedJsonEncoder)

    return state
