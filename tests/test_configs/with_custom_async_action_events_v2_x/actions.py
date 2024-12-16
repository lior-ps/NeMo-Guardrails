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

import asyncio

from nemoguardrails.actions import action
from nemoguardrails.colang.v2_x.runtime.runtime import ActionEventHandler


@action(name="CustomAsyncTest1Action", is_system_action=True, execute_async=True)
async def custom_async_test1(event_handler: ActionEventHandler):
    for i in range(1, 3):
        await asyncio.sleep(1)
        event_handler.send_action_updated_event("Value", {"number": i})
    await asyncio.sleep(1)
    event_handler.send_event("CustomEventA", {"value": "A"})
    events = await event_handler.wait_for_events("CustomEventB")
    event_handler.send_event("CustomEventResponse", {"value": events[0]["value"]})
    await event_handler.wait_for_events("CustomEventC")
    await asyncio.sleep(3)
    # raise Exception("Python action exception!")


@action(name="CustomAsyncTest2Action", is_system_action=True, execute_async=True)
async def custom_async_test2(event_handler: ActionEventHandler):
    await event_handler.wait_for_events("CustomEventResponse")
    await asyncio.sleep(3)
    event_handler.send_event("CustomEventC", {"value": "C"})
