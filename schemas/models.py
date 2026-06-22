from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import enum


class SupervisorMode(str, enum.Enum):
    observe_only = "observe_only"
    human_review = "human_review"
    auto_fix = "auto_fix"


class RequirementItem(BaseModel):
    id: str
    title: str
    description: str
    completed: bool = False
    category: str = "general"
    source_section: Optional[str] = None
    source_line: Optional[int] = None
    status: str = "pending"


class BuildResult(BaseModel):
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    duration_seconds: Optional[float] = None
    execution_mode: str = "argv"
    failure_type: str = "success"


class TestResult(BaseModel):
    success: bool
    name: str
    details: str = ""
    screenshots: List[str] = Field(default_factory=list)
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)


class BugReport(BaseModel):
    bug_id: str
    severity: str
    page_url: Optional[str] = None
    title: str
    steps_to_reproduce: List[str]
    expected: str
    actual: str
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)
    suggested_fix_area: Optional[str] = None


class FinalReport(BaseModel):
    requirement_coverage: float
    build_passed: bool
    tests_passed: bool
    fixed_bugs: int
    remaining_bugs: int
    readiness_score: int
    recommendation: str
    details: Dict[str, Any] = Field(default_factory=dict)


class SupervisorStatus(str, enum.Enum):
    idle = "idle"
    running = "running"
    paused = "paused"
    stopped = "stopped"
    human_review_required = "human_review_required"
    completed = "completed"


class ScreenAnalysis(BaseModel):
    active_app: Optional[str] = None
    visible_window_title: Optional[str] = None
    current_activity: Optional[str] = None
    coding_agent_visible: bool = False
    vscode_visible: bool = False
    cursor_visible: bool = False
    terminal_visible: bool = False
    browser_visible: bool = False
    permission_prompt_visible: bool = False
    permission_button_text: Optional[str] = None
    permission_button_bbox: Optional[List[int]] = None
    error_visible: bool = False
    error_text: Optional[str] = None
    file_being_edited: Optional[str] = None
    command_visible: Optional[str] = None
    completion_claimed: bool = False
    stuck_detected: bool = False
    risky_action_detected: bool = False
    vision_analysis_failed: bool = False
    summary: str = ""
    recommended_action: str = "continue_watching"
    recommended_prompt: Optional[str] = None


class SupervisorDecision(str, enum.Enum):
    continue_watching = "continue_watching"
    click_safe_permission = "click_safe_permission"
    pause_for_human_review = "pause_for_human_review"
    type_prompt_to_coding_agent = "type_prompt_to_coding_agent"
    suggest_prompt_to_human = "suggest_prompt_to_human"
    run_build_validation = "run_build_validation"
    run_qa_validation = "run_qa_validation"
    send_bug_fix_prompt = "send_bug_fix_prompt"
    send_next_task_prompt = "send_next_task_prompt"
    mark_task_complete = "mark_task_complete"
    mark_project_complete = "mark_project_complete"
    stop_due_to_risky_action = "stop_due_to_risky_action"


class SupervisorState(BaseModel):
    status: SupervisorStatus = SupervisorStatus.idle
    supervisor_mode: str = "human_review"
    current_task: str = ""
    last_screen_analysis: Optional[Dict[str, Any]] = None
    last_decision: str = ""
    last_prompt_sent: str = ""
    suggested_prompt: Optional[str] = None
    waiting_for: str = ""
    risk_detected: bool = False
    human_review_reason: Optional[str] = None
    current_stage: str = ""
