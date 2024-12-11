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
from nemoguardrails.actions.action_dispatcher import ActionEventGenerator


@action(name="CustomAsyncTestAction", is_system_action=True, execute_async=True)
async def custom_async_test(event_generator: ActionEventGenerator):
    for i in range(1, 5):
        await asyncio.sleep(1)
        event_generator.send_action_updated_event("Value", {"number": i})
    await asyncio.sleep(1)
    event_generator.send_raw_event("NewCustomUmimEvent", {"secret": "xyz"})
    await asyncio.sleep(1)
