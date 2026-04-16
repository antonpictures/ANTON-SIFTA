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
# Fixed Code Structure
# All imports must be at the top level.
from typing import List, Dict, Any
import json
# Assume necessary class/module definitions here...

class ReportGenerator:
    """
    Generates and validates operational reports.
    """
    def __init__(self, history: List[Dict[str, Any]], name: str):
        self.history = history
        self.name = name

    def add_stage(self, name: str, detail: str):
        """Adds a stage entry to the history."""
        self.history.append({"stage": name, "detail": detail})

    def run_validation_flow(self, record: dict) -> dict:
        """
        Example method demonstrating a core workflow.
        """
        # This structure assumes the floating code block was meant to be inside a method
        # and uses a standard return flow.
        try:
            # Example logic placeholder
            result = {"status": "success", "message": "Validation complete."}
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_report(self) -> dict:
        """
        Compiles and returns a structured report dictionary.
        Ensures all structures (like 'stages') are properly closed.
        """
        report = {
            "generator_name": self.name,
            "report_date": "YYYY-MM-DD",
            "stages": [
                # Add stages dynamically or manually
                {"stage_id": 1, "status": "Completed", "data": "Initial check passed."},
                {"stage_id": 2, "status": "Running", "data": "Processing records."},
                # The list must be properly terminated
            ]
        }
        return report

    def validate(self, record: dict) -> bool:
        """
        Performs comprehensive data validation checks.
        """
        # Validation logic goes here.
        if not isinstance(record, dict):
            print("Validation Failed: Record must be a dictionary.")
            return False
        
        # Example validation check: ensure required keys exist
        required_keys = ["id", "timestamp"]
        if not all(key in record for key in required_keys):
            print(f"Validation Failed: Missing required keys: {required_keys}")
            return False
        
        return True
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
