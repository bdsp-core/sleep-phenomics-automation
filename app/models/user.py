from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Integer, String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from .. import db
import enum
import json

class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    last_login: Mapped[datetime] = mapped_column(default=datetime.now())
    files: Mapped[list["PSGFile"]] = relationship("PSGFile", back_populates="owner", cascade="all, delete-orphan")
    
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<User {self.email}>'
class PSGFileType(enum.Enum):
    EDF = "edf"
    BDF = "bdf"
    SPECTROGRAM = "npz"

class DerivedFile(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    psg_file_id: Mapped[int] = mapped_column(ForeignKey("psg_file.id"))
    file_type: Mapped[str]  # or use enum
    storage_path: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=datetime.now())
    file_size: Mapped[int]

    psg_file: Mapped["PSGFile"] = relationship(back_populates="derived_files")

class PSGFile(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str]
    original_filename: Mapped[str]
    upload_date: Mapped[datetime] = mapped_column(default=datetime.now())
    file_size: Mapped[int]
    storage_path: Mapped[str]

    # Recording metadata
    sampling_rate: Mapped[float]
    num_channels: Mapped[int]
    duration: Mapped[float]
    recording_date: Mapped[datetime]

    # User relationship
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    owner: Mapped["User"] = relationship("User", back_populates="files")

    derived_files: Mapped[list["DerivedFile"]] = relationship(back_populates="psg_file", cascade="all, delete-orphan")
    channel_mappings: Mapped[list["ChannelMapping"]] = relationship(back_populates="psg_file", cascade="all, delete-orphan")

    def get_derived_file(self, file_type: PSGFileType) -> Optional[DerivedFile]:
        """Get a specific derived file if it exists."""
        return next((f for f in self.derived_files if f.file_type == file_type.value), None)
    
    def get_channel_mapping(self) -> dict:
        """Get the channel mapping dictionary for this file."""
        mapping = {}
        for cm in self.channel_mappings:
            mapping[cm.standard_channel] = cm.edf_channel
        return mapping
    
    def set_channel_mapping(self, mapping_dict: dict):
        """Set the channel mapping for this file."""
        # Clear existing mappings
        self.channel_mappings.clear()
        
        # Add new mappings
        for standard_channel, edf_channel in mapping_dict.items():
            if edf_channel:  # Only add non-empty mappings
                channel_mapping = ChannelMapping(
                    psg_file=self,
                    standard_channel=standard_channel,
                    edf_channel=edf_channel
                )
                self.channel_mappings.append(channel_mapping)

    def __repr__(self):
        return f'<PSGFile {self.original_filename}>'


class ChannelMapping(db.Model):
    """Stores the mapping between standard PSG channels and EDF file channels."""
    id: Mapped[int] = mapped_column(primary_key=True)
    psg_file_id: Mapped[int] = mapped_column(ForeignKey("psg_file.id"))
    standard_channel: Mapped[str] = mapped_column(String(50))  # e.g., "F3-M2"
    edf_channel: Mapped[str] = mapped_column(String(100))      # e.g., "EEG F3-REF"
    created_at: Mapped[datetime] = mapped_column(default=datetime.now())

    psg_file: Mapped["PSGFile"] = relationship(back_populates="channel_mappings")
    
    def __repr__(self):
        return f'<ChannelMapping {self.standard_channel}->{self.edf_channel}>'