# Copyright 2024 AstroLab Software
# Author: Sergey Karpov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""callback_telemetry.py -- Extend Dash to include logging of callbacks w/ context"""

import inspect
import time
from functools import wraps

from dash import Dash, callback_context

from colorama import Fore, Style

LOG_CALLBACK_TELEMETRY = True

# Borrowed from https://community.plotly.com/t/log-every-dash-callback-including-context-for-debug/74828/5


def callback_telemetry(func):
    """Wrapper to provide telemetry for dash callbacks"""

    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        def get_callback_ref(func_ref):
            module = inspect.getmodule(func_ref)
            return f"{module.__name__.split('.')[-1]}:{func_ref.__name__}"

        def flatten(arg):
            if not isinstance(arg, list):  # if not list
                return [arg]
            return [x for sub in arg for x in flatten(sub)]

        def generate_results_dict(function_output, outputs_list):
            if isinstance(function_output, tuple) or isinstance(outputs_list, list):
                output_strs = [
                    f"{output}.{output['property']}" for output in flatten(outputs_list)
                ]
                return dict(zip(output_strs, flatten(function_output)))
            return {f"{outputs_list['id']}.{outputs_list['property']}": function_output}

        def format_callback_dict(data):
            return "||".join([f"{key}:{str(data[key])[:20]}" for key in data])

        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time

        results_dict = generate_results_dict(result, callback_context.outputs_list)

        inputs_str = format_callback_dict(callback_context.inputs)
        state_str = format_callback_dict(callback_context.states)
        result_str = format_callback_dict(results_dict)

        context = (
            f"___input:|{inputs_str}|\n___state:|{state_str}|\n__output:|{result_str}|"
        )

        print(
            f"{Fore.BLUE}[TELEMETRY]{Style.RESET_ALL} {Style.BRIGHT}{Fore.RED}{get_callback_ref(func)}{Style.RESET_ALL}, {total_time:.4f}s\n{context}"
        )

        return result

    return timeit_wrapper


class DashWithTelemetry(Dash):
    """Provide logging telemetry for Dash callbacks"""

    def callback(self, *_args, **_kwargs):
        def decorator(function):
            def wrapper(*args, **kwargs):
                if LOG_CALLBACK_TELEMETRY:
                    retval = (callback_telemetry)(function)(*args, **kwargs)
                else:
                    retval = function(*args, **kwargs)

                return retval

            fn = super(DashWithTelemetry, self).callback(*_args, **_kwargs)
            return (fn)(wrapper)

        return decorator
