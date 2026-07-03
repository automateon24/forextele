"""
🧪 TEST CONFIGURATION
==================
Configuration for comprehensive testing framework
"""

# Test configuration
TEST_CONFIG = {
    "test_suites": {
        "sanity_tests": {
            "enabled": True,
            "timeout": 30,
            "critical": True
        },
        "security_tests": {
            "enabled": True,
            "timeout": 60,
            "critical": True
        },
        "unit_tests": {
            "enabled": True,
            "timeout": 45,
            "critical": False
        },
        "functional_tests": {
            "enabled": True,
            "timeout": 120,
            "critical": True
        },
        "data_fetching_tests": {
            "enabled": True,
            "timeout": 120,
            "critical": True
        },
        "race_condition_tests": {
            "description": "Race condition detection and thread safety",
            "tests": [
                "Shared Memory Race Condition",
                "Concurrent Data Access",
                "Memory Pool Race Condition",
                "CSV File Race Condition",
                "Thread Safe Counters",
                "Queue Race Condition",
                "Lock Contention",
                "Data Consistency",
                "Resource Cleanup",
                "Graceful Shutdown",
                "High Concurrency Stress",
                "Deadlock Detection",
                "Atomic Operations",
                "Data Corruption Detection",
                "Thread Safety Violations"
            ]
        },
        "critical_issues": {
            "enabled": True,
            "timeout": 180,
            "critical": True
        }
    },
    
    "project_structure": {
        "required_directories": [
            "logs",
            "trades", 
            "reports",
            "config",
            "scripts",
            "TEST_FRAMEWORK"
        ],
        "required_files": [
            "config/system_config.yaml",
            ".env.template"
        ]
    },
    
    "security": {
        "forbidden_patterns": [
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9",
            "1101936133",
            "password",
            "secret",
            "token",
            "key",
            "auth"
        ],
        "required_env_vars": [
            "DHAN_CLIENT_ID",
            "DHAN_ACCESS_TOKEN"
        ]
    },
    
    "performance": {
        "max_response_time": 5000,  # milliseconds
        "max_memory_usage": 512,    # MB
        "max_cpu_usage": 80,        # percentage
        "max_thread_count": 50
    },
    
    "critical_thresholds": {
        "max_failure_rate": 10,     # percentage
        "max_error_count": 5,
        "max_timeout_count": 3
    },
    
    "notifications": {
        "email": {
            "enabled": False,
            "smtp_server": "",
            "recipients": []
        },
        "slack": {
            "enabled": False,
            "webhook_url": ""
        }
    }
}

# Test categories and descriptions
TEST_CATEGORIES = {
    "sanity_tests": {
        "description": "Basic system health checks",
        "tests": [
            "Project Structure",
            "Configuration Files", 
            "API Connection",
            "Dependencies",
            "Data Directories",
            "Logging System",
            "Environment Setup",
            "Basic Imports"
        ]
    },
    
    "security_tests": {
        "description": "Security vulnerability checks",
        "tests": [
            "Credential Security",
            "API Key Exposure",
            "File Permissions",
            "Environment Variables",
            "Hardcoded Secrets",
            "SSL/TLS Security",
            "Input Validation",
            "SQL Injection",
            "XSS Protection",
            "Authentication"
        ]
    },
    
    "unit_tests": {
        "description": "Individual component testing",
        "tests": [
            "Strategy Logic Tests",
            "Data Processing Tests",
            "Calculation Tests",
            "API Response Parsing",
            "Configuration Loading",
            "Logging Functions",
            "Error Handling",
            "Utility Functions",
            "Data Validation",
            "Performance Metrics"
        ]
    },
    
    "functional_tests": {
        "description": "End-to-end functionality testing",
        "tests": [
            "End-to-End Trading Flow",
            "Strategy Execution",
            "Market Data Integration",
            "Trade Logging",
            "Risk Management",
            "Performance Tracking",
            "Error Recovery",
            "Multi-threading",
            "Data Persistence",
            "API Integration"
        ]
    },
    
    "data_fetching_tests": {
        "description": "Data fetching thread functionality",
        "tests": [
            "Thread Initialization",
            "API Connection",
            "Expiry List Fetch",
            "Market Data Fetch",
            "Options Chain Fetch",
            "Memory Pool Update",
            "CSV Logging",
            "Thread Safety",
            "Data Synchronization",
            "Performance Metrics",
            "Error Handling",
            "Data Access Methods",
            "ATM Options",
            "Statistics",
            "Thread Lifecycle"
        ]
    },
    
    "race_condition_tests": {
            "description": "Race condition detection and thread safety",
            "tests": [
                "Shared Memory Race Condition",
                "Concurrent Data Access",
                "Memory Pool Race Condition",
                "CSV File Race Condition",
                "Thread Safe Counters",
                "Queue Race Condition",
                "Lock Contention",
                "Data Consistency",
                "Resource Cleanup",
                "Graceful Shutdown",
                "High Concurrency Stress",
                "Deadlock Detection",
                "Atomic Operations",
                "Data Corruption Detection",
                "Thread Safety Violations"
            ]
        },
        "critical_issues": {
        "description": "Critical system issue detection",
        "tests": [
            "Memory Leaks",
            "Race Conditions",
            "Deadlock Detection",
            "Resource Exhaustion",
            "Data Corruption",
            "Infinite Loops",
            "Stack Overflow",
            "Connection Pooling",
            "Transaction Integrity",
            "System Stability"
        ]
    }
}

# Test execution modes
EXECUTION_MODES = {
    "quick": {
        "description": "Quick sanity check only",
        "suites": ["sanity_tests"],
        "timeout": 60
    },
    "standard": {
        "description": "Standard testing suite",
        "suites": ["sanity_tests", "security_tests", "unit_tests"],
        "timeout": 300
    },
    "comprehensive": {
        "description": "Full comprehensive testing",
        "suites": ["sanity_tests", "security_tests", "unit_tests", "functional_tests", "data_fetching_tests", "race_condition_tests", "critical_issues"],
        "timeout": 900
    },
    "production": {
        "description": "Production readiness testing",
        "suites": ["sanity_tests", "security_tests", "functional_tests", "data_fetching_tests", "race_condition_tests", "critical_issues"],
        "timeout": 1080
    }
}

# Test result thresholds
TEST_THRESHOLDS = {
    "critical": {
        "min_success_rate": 100,  # Must pass all critical tests
        "max_failures": 0
    },
    "high": {
        "min_success_rate": 95,
        "max_failures": 2
    },
    "medium": {
        "min_success_rate": 80,
        "max_failures": 5
    },
    "low": {
        "min_success_rate": 70,
        "max_failures": 10
    }
}

# Test environment settings
TEST_ENVIRONMENT = {
    "development": {
        "timeout_multiplier": 1.0,
        "parallel_execution": True,
        "detailed_logging": True
    },
    "staging": {
        "timeout_multiplier": 1.5,
        "parallel_execution": True,
        "detailed_logging": True
    },
    "production": {
        "timeout_multiplier": 2.0,
        "parallel_execution": False,
        "detailed_logging": False
    }
}
