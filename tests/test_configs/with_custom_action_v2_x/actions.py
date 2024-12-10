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
from typing import Optional

from nemoguardrails.actions import action
from nemoguardrails.actions.action_dispatcher import ActionEventGenerator


@action(name="CustomTestAction", is_system_action=True, execute_async=True)
async def custom_test(context: dict, param: int, event_generator: ActionEventGenerator):
    for i in range(1, 5):
        await asyncio.sleep(5)
        await event_generator.send_action_update_event("Test", {f"value {i}": 10})
    return param + context["value"]


@action(name="CustomActionWithUpdateEventsAction")
async def custom_action_with_update_events(context: Optional[dict] = None, **kwargs):
    return True
