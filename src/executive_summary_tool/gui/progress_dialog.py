"""Progress dialog for long-running operations."""

from typing import Optional, Callable
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QProgressBar, QPushButton, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont


class ProgressDialog(QDialog):
    """Dialog for showing progress of long-running operations."""
    
    # Signals
    cancelled = Signal()
    
    def __init__(self, title: str = "Processing", parent=None):
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # State
        self.is_cancelled = False
        self.cancel_callback: Optional[Callable] = None
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Main message
        self.main_label = QLabel("Processing...")
        self.main_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.main_label.setFont(font)
        layout.addWidget(self.main_label)
        
        # Detail message
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Log area (initially hidden)
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(80)
        self.log_text.setVisible(False)
        layout.addWidget(self.log_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.show_log_btn = QPushButton("Show Log")
        self.show_log_btn.clicked.connect(self.toggle_log)
        button_layout.addWidget(self.show_log_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Timer for indeterminate progress
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.pulse_progress)
        self.pulse_value = 0
        self.pulse_direction = 1
    
    def set_message(self, message: str):
        """Set the main message."""
        self.main_label.setText(message)
    
    def set_detail(self, detail: str):
        """Set the detail message."""
        self.detail_label.setText(detail)
    
    def set_progress(self, value: int):
        """Set progress value (0-100)."""
        if self.pulse_timer.isActive():
            self.pulse_timer.stop()
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(max(0, min(100, value)))
    
    def set_indeterminate(self):
        """Set indeterminate progress (pulsing)."""
        self.progress_bar.setRange(0, 0)
        self.pulse_timer.start(50)  # 50ms pulse
    
    def pulse_progress(self):
        """Animate indeterminate progress."""
        self.pulse_value += self.pulse_direction * 2
        
        if self.pulse_value >= 100:
            self.pulse_direction = -1
        elif self.pulse_value <= 0:
            self.pulse_direction = 1
        
        self.progress_bar.setValue(self.pulse_value)
    
    def add_log_message(self, message: str):
        """Add a message to the log."""
        self.log_text.append(message)
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)
    
    def toggle_log(self):
        """Toggle log visibility."""
        if self.log_text.isVisible():
            self.log_text.setVisible(False)
            self.show_log_btn.setText("Show Log")
            self.setFixedSize(400, 200)
        else:
            self.log_text.setVisible(True)
            self.show_log_btn.setText("Hide Log")
            self.setFixedSize(400, 300)
    
    def set_cancel_callback(self, callback: Callable):
        """Set callback function for cancel operation."""
        self.cancel_callback = callback
    
    def enable_cancel(self, enabled: bool = True):
        """Enable or disable cancel button."""
        self.cancel_btn.setEnabled(enabled)
    
    def cancel_operation(self):
        """Cancel the current operation."""
        self.is_cancelled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        
        if self.cancel_callback:
            self.cancel_callback()
        
        self.cancelled.emit()
    
    def complete(self, success: bool = True, message: str = None):
        """Mark operation as complete."""
        self.pulse_timer.stop()
        
        if success:
            self.progress_bar.setValue(100)
            self.main_label.setText(message or "Completed successfully")
            self.cancel_btn.setText("Close")
        else:
            self.main_label.setText(message or "Operation failed")
            self.cancel_btn.setText("Close")
        
        # Disconnect cancel functionality
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        if not self.is_cancelled and self.cancel_btn.isEnabled():
            self.cancel_operation()
        
        self.pulse_timer.stop()
        event.accept()


class WorkflowProgressDialog(ProgressDialog):
    """Enhanced progress dialog for workflow operations."""
    
    def __init__(self, parent=None):
        super().__init__("Executive Summary Generation", parent)
        
        # Workflow stages
        self.stages = [
            "Validating configuration",
            "Connecting to Jira",
            "Fetching activity data",
            "Processing data",
            "Generating AI summary",
            "Creating document",
            "Finalizing"
        ]
        
        self.current_stage = 0
        self.total_stages = len(self.stages)
        
        # Update UI for workflow
        self.setFixedSize(450, 220)
        
        # Add stage indicator
        self.stage_label = QLabel(f"Stage 1 of {self.total_stages}")
        self.stage_label.setAlignment(Qt.AlignCenter)
        
        # Insert stage label after main label
        layout = self.layout()
        layout.insertWidget(1, self.stage_label)
    
    def start_stage(self, stage_index: int):
        """Start a specific stage."""
        if 0 <= stage_index < self.total_stages:
            self.current_stage = stage_index
            stage_name = self.stages[stage_index]
            
            self.set_message(f"Step {stage_index + 1}: {stage_name}")
            self.stage_label.setText(f"Stage {stage_index + 1} of {self.total_stages}")
            
            # Update overall progress
            overall_progress = int((stage_index / self.total_stages) * 100)
            self.set_progress(overall_progress)
            
            self.add_log_message(f"Started: {stage_name}")
    
    def complete_stage(self, stage_index: int, success: bool = True):
        """Complete a specific stage."""
        if 0 <= stage_index < self.total_stages:
            stage_name = self.stages[stage_index]
            
            if success:
                self.add_log_message(f"Completed: {stage_name}")
            else:
                self.add_log_message(f"Failed: {stage_name}")
                
            # Update overall progress
            overall_progress = int(((stage_index + 1) / self.total_stages) * 100)
            self.set_progress(overall_progress)
    
    def next_stage(self):
        """Move to the next stage."""
        if self.current_stage < self.total_stages - 1:
            self.complete_stage(self.current_stage, True)
            self.start_stage(self.current_stage + 1)
    
    def fail_stage(self, error_message: str = None):
        """Mark current stage as failed."""
        self.complete_stage(self.current_stage, False)
        
        error_msg = error_message or f"Failed during: {self.stages[self.current_stage]}"
        self.complete(False, error_msg)
    
    def complete_workflow(self):
        """Complete the entire workflow."""
        if self.current_stage < self.total_stages - 1:
            # Complete remaining stages
            for i in range(self.current_stage, self.total_stages):
                self.complete_stage(i, True)
        
        self.complete(True, "Executive summary generated successfully!")


class SimpleProgressDialog(ProgressDialog):
    """Simplified progress dialog for basic operations."""
    
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(title, parent)
        
        self.setFixedSize(350, 150)
        self.set_message(message)
        self.set_indeterminate()
        
        # Hide log button for simple operations
        self.show_log_btn.setVisible(False)
    
    def update_message(self, message: str):
        """Update the progress message."""
        self.set_message(message)