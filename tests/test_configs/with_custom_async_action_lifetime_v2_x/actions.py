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


@action(name="Test1Action", is_system_action=True, execute_async=True)
async def test1():
    await asyncio.sleep(1)


@action(name="Test2Action", is_system_action=True, execute_async=True)
async def test2(event_handler: ActionEventHandler):
    await event_handler.wait_for_events("NeverHappeningEver")


@action(name="Test3Action", is_system_action=True, execute_async=True)
async def test3(event_handler: ActionEventHandler):
    raise Exception("Issue occurred!")
