"""
SQL-specific Pydantic schemas for the text-to-SQL agent
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ColumnType(str, Enum):
    """Database column types"""
    INTEGER = "INTEGER"
    TEXT = "TEXT"
    REAL = "REAL"
    BLOB = "BLOB"
    VARCHAR = "VARCHAR"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"


class Column(BaseModel):
    """Database column definition"""
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Column data type")
    primary_key: bool = Field(default=False, description="Is primary key")
    nullable: bool = Field(default=True, description="Can be NULL")
    description: Optional[str] = Field(None, description="Column description")


class ForeignKey(BaseModel):
    """Foreign key relationship"""
    column: str = Field(..., description="Column name in source table")
    referenced_table: str = Field(..., description="Referenced table name")
    referenced_column: str = Field(..., description="Referenced column name")


class Table(BaseModel):
    """Database table definition"""
    name: str = Field(..., description="Table name")
    columns: List[Column] = Field(..., description="List of columns")
    foreign_keys: List[ForeignKey] = Field(default_factory=list, description="Foreign key relationships")
    description: Optional[str] = Field(None, description="Table description")


class DatabaseSchema(BaseModel):
    """Complete database schema"""
    name: str = Field(default="database", description="Database name")
    tables: List[Table] = Field(..., description="List of tables")
    
    def to_prompt_format(self) -> str:
        """Convert schema to CREATE TABLE format for SQL generation"""
        schema_lines = []
        
        for table in self.tables:
            # CREATE TABLE statement
            create_stmt = f"CREATE TABLE {table.name} (\n"
            
            col_definitions = []
            for col in table.columns:
                col_def = f"  {col.name} {col.type}"
                if col.primary_key:
                    col_def += " PRIMARY KEY"
                if not col.nullable:
                    col_def += " NOT NULL"
                col_definitions.append(col_def)
            
            # Add foreign keys
            for fk in table.foreign_keys:
                fk_def = f"  FOREIGN KEY ({fk.column}) REFERENCES {fk.referenced_table}({fk.referenced_column})"
                col_definitions.append(fk_def)
            
            create_stmt += ",\n".join(col_definitions)
            create_stmt += "\n);"
            
            # Add comment if description exists
            if table.description:
                create_stmt += f"  -- {table.description}"
            
            schema_lines.append(create_stmt)
        
        return "\n\n".join(schema_lines)


class SQLRequest(BaseModel):
    """Request to generate SQL from natural language"""
    question: str = Field(..., description="Natural language question")
    db_schema: DatabaseSchema = Field(..., alias="schema", description="Database schema")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for context")
    execute: bool = Field(default=False, description="Whether to execute the generated SQL")
    max_rows: int = Field(default=100, description="Maximum rows to return if executing")

    model_config = {"populate_by_name": True}


class ValidationError(BaseModel):
    """SQL validation error"""
    error_type: str = Field(..., description="Type of validation error")
    message: str = Field(..., description="Error message")
    severity: str = Field(..., description="Error severity: warning, error, critical")


class SQLResponse(BaseModel):
    """Response containing generated SQL"""
    sql: str = Field(..., description="Generated SQL query")
    explanation: Optional[str] = Field(None, description="Explanation of the query")
    is_valid: bool = Field(..., description="Whether the SQL passed validation")
    validation_errors: List[ValidationError] = Field(default_factory=list, description="Validation errors")
    confidence: Optional[float] = Field(None, description="Model confidence score")


class QueryResult(BaseModel):
    """SQL query execution result"""
    columns: List[str] = Field(..., description="Column names")
    rows: List[List[Any]] = Field(..., description="Result rows")
    row_count: int = Field(..., description="Number of rows returned")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


class SQLExecuteRequest(BaseModel):
    """Request to execute SQL"""
    sql: str = Field(..., description="SQL query to execute")
    db_schema: DatabaseSchema = Field(..., alias="schema", description="Database schema for validation")
    max_rows: int = Field(default=100, description="Maximum rows to return")
    timeout_seconds: int = Field(default=30, description="Query timeout in seconds")

    model_config = {"populate_by_name": True}


class SQLExecuteResponse(BaseModel):
    """Response from SQL execution"""
    success: bool = Field(..., description="Whether execution succeeded")
    result: Optional[QueryResult] = Field(None, description="Query results if successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    sql_validated: bool = Field(..., description="Whether SQL passed safety validation")
