import json
import time
from pathlib import Path
from typing import Callable, List, Optional, Any

# Define a type alias for pipeline stages for clarity
StageFunction = Callable[[Any], Any]

class Pipeline:
    """Multi-stage data processing pipeline.

    Manages a sequence of data transformations (stages) applied to an initial input.
    Each stage is expected to take data and return transformed data.
    """

    def __init__(self, name: str):
        """
        Initializes the pipeline.

        Args:
            name: A descriptive name for the pipeline instance.
        """
        self.name = name
        # stages stores dictionaries defining the stage (e.g., {"function": ..., "kwargs": {...}})
        self.stages: List[dict] = []
        # history records the state and output after each execution stage
        self.history: List[dict] = []

    def add_stage(self, function: StageFunction, stage_name: str, **kwargs: Any) -> None:
        """
        Adds a transformation stage to the pipeline.

        Args:
            function: The callable function representing the transformation.
            stage_name: A readable name for the stage.
            **kwargs: Keyword arguments to be passed to the function.
        """
        if not callable(function):
            raise TypeError("The stage must be provided with a callable function.")
        
        self.stages.append({
            "function": function,
            "name": stage_name,
            "kwargs": kwargs
        })

    def run(self, initial_data: Any) -> Any:
        """
        Executes the data through all defined stages sequentially.

        Args:
            initial_data: The raw input data for the pipeline.

        Returns:
            The final processed data after all stages have executed.
        """
        current_data = initial_data
        self.history = []

        print(f"--- Running Pipeline: {self.name} ---")

        for i, stage_config in enumerate(self.stages):
            stage_func = stage_config["function"]
            stage_name = stage_config["name"]
            kwargs = stage_config["kwargs"]
            
            try:
                print(f"[{i+1}/{len(self.stages)}] Executing Stage: {stage_name}...")
                
                # Execute the stage function with current data and specified kwargs
                current_data = stage_func(current_data, **kwargs)
                
                # Record history
                self.history.append({
                    "stage_name": stage_name,
                    "input_type": type(current_data).__name__, # Note: capturing the input type before transformation is better, but simplifying for now.
                    "output": current_data
                })
                print(f"  -> Stage successful. Output type: {type(current_data).__name__}")
                
            except Exception as e:
                print(f"ERROR: Stage '{stage_name}' failed: {e}")
                # Stop execution and return the data up to the point of failure
                return current_data, f"Pipeline failed at stage '{stage_name}' due to error: {e}"

        print("--- Pipeline Execution Complete ---")
        return current_data, "Successfully completed."
    def add_stage(self, stage_name: str, processor: Callable, priority: int = 0):
        self.stages.append({
            "name": stage_name,
            "processor": processor,
            "priority": priority,
"executions": 0
        })
        self.stages.sort(key=lambda s: s["priority"], reverse=True)

    def execute(self, data: dict) -> dict:
        result = data.cpy()
        trace = []
        for stage in self.stages:
            start = time.time()
            try:
                result = stage["processor"](result)
                stage["executions"] += 1
                trace.append({
                    "stage": stage["name"],
                    "duration": time.time() - start,
                    "status": "ok"
                })
            except Exception as e:
                trace.append({
                    "stage": stage["name"],
                    "duration": time.time() - start,
                    "status": "error",
                    "message": str(e)
Syntax Errors Detected:

1.  **Misplaced Import Statement:** The line `from typing import List` is found within the body of the code structure (after `stages": [`). Import statements must be placed at the top level of the module, before any class or function definitions.

2.  **Scope and Structure Violation (Fragmentation):** The code block is severely fragmented, mixing code intended for multiple scopes.
    *   The code block containing `self.history.append(...)` and `return result` appears floating and is not contained within a definition (class, method, or function) that would define `self.history` or `self.name`.
    *   The `def get_report(self) -> dict:` method is interrupted by a structural jump (`from typing import List`).

3.  **Incomplete Method Definition:** The method `get_report(self) -> dict:` is syntactically incomplete. The `stages` list starts (`"stages": [`) but is never closed, leading to an `SyntaxError` or `TypeError` upon compilation due to missing list elements or improper termination.

**Suggested Structural Fixes:**

1.  **Move Imports:** Relocate all `from ... import ...` statements to the absolute beginning of the file.
2.  **Scope Isolation:** Ensure that all code segments belong logically within a defined function or method. The floating code must be correctly incorporated into a parent function.
3.  **Complete Logic:** Close all open structures (e.g., add the remaining logic and the closing brackets/braces for the `stages` list within `get_report`).

    def validate(self, record: dict) -> bool:
        """
        Performs comprehensive data validation checks.
        Returns True if valid, False otherwise.
        """
        self.errors = []
        
        # 1. Check for missing required fields
        for field in self.REQUIRED_FIELDS:
            if field not in record:
                self.errors.append(f"Missing required field: {field}")
        
        # 2. Check structural/type constraints (e.g., payload must be a dictionary)
        if "payload" in record and not isinstance(record["payload"], dict):
            self.errors.append("Payload must be a dictionary")
            
        # 3. Determine validity based on rules
        if self.errors:
            # If there are errors, the record is invalid.
            return False
        
        # If validation passes:
        return True

    def get_errors(self) -> List[str]:
        """Returns a copy of the validation errors found."""
        return self.errors.copy()
