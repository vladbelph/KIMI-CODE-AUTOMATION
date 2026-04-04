"""PARA models - Projects, Areas, Resources, Archives."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, 
    ForeignKey, Integer, Boolean, JSON, UUID, func
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class ProjectStatus(str, Enum):
    """Project status enum."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class TaskStatus(str, Enum):
    """Task status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResourceType(str, Enum):
    """Resource type enum."""
    DOCS = "docs"
    PATTERNS = "patterns"
    CODEBASE_MAP = "codebase_map"
    API_SCHEMAS = "api_schemas"
    CONFIG = "config"


class Project(Base):
    """Projects table - individual deliverables with goals and deadlines."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    repo_path = Column(String(512), nullable=False)
    spec_path = Column(String(512), nullable=True)
    status = Column(String(50), default=ProjectStatus.ACTIVE.value)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    areas = relationship("Area", back_populates="project", cascade="all, delete-orphan")
    archives = relationship("Archive", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"


class Area(Base):
    """Areas table - spheres of activity with ongoing maintenance."""
    __tablename__ = "areas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    responsibility_scope = Column(Text, nullable=True)  # What belongs to this area
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="areas")
    resources = relationship("Resource", back_populates="area", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Area(id={self.id}, name={self.name})>"


class Resource(Base):
    """Resources table - reference materials and knowledge base."""
    __tablename__ = "resources"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id"), nullable=False)
    type = Column(String(50), nullable=False)  # docs, patterns, codebase_map, api_schemas
    content = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # For semantic search
    meta = Column(JSON, nullable=True)
    file_path = Column(String(512), nullable=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    area = relationship("Area", back_populates="resources")
    
    def __repr__(self):
        return f"<Resource(id={self.id}, type={self.type}, title={self.title})>"


class Archive(Base):
    """Archives table - completed tasks and lessons learned."""
    __tablename__ = "archives"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)
    task_description = Column(Text, nullable=True)
    execution_log = Column(Text, nullable=True)
    success = Column(Boolean, nullable=True)
    lessons_learned = Column(ARRAY(String), nullable=True)
    files_modified = Column(ARRAY(String), nullable=True)
    commit_hash = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="archives")
    
    def __repr__(self):
        return f"<Archive(id={self.id}, success={self.success})>"


class Task(Base):
    """Tasks table - execution queue."""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    spec_path = Column(String(512), nullable=False)
    status = Column(String(50), default=TaskStatus.PENDING.value)
    priority = Column(Integer, default=5)  # 1-10, lower is higher priority
    yolo_mode = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_log = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    
    # Kimi CLI specific fields
    kimi_tokens_used = Column(Integer, nullable=True)
    kimi_exit_code = Column(Integer, nullable=True)
    llm_provider = Column(String(50), default="kimi_cli")  # kimi_cli, openai, anthropic, etc.
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    
    def __repr__(self):
        return f"<Task(id={self.id}, status={self.status}, priority={self.priority})>"


class DatabaseManager:
    """Database manager for PARA models."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables."""
        # Enable pgvector extension
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(self.engine)
    
    def drop_tables(self):
        """Drop all tables (use with caution)."""
        Base.metadata.drop_all(self.engine)
    
    def get_session(self):
        """Get database session."""
        return self.SessionLocal()
    
    def find_similar_resources(self, query_embedding: List[float], limit: int = 5) -> List[Resource]:
        """Find resources by semantic similarity."""
        session = self.get_session()
        try:
            # Using cosine similarity for vector search
            results = session.query(Resource).order_by(
                Resource.embedding.cosine_distance(query_embedding)
            ).limit(limit).all()
            return results
        finally:
            session.close()


from sqlalchemy import text
