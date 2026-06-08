"""Data models for the apartment management system.

The module contains Pydantic models used to deserialize JSON input files and to
represent the typed entities consumed by :class:`src.manager.Manager`.
"""

import json

from pydantic import BaseModel, Field


class Parameters(BaseModel):
    """Configuration parameters for data loading and validation rules."""

    apartments_json_path: str = Field(
        default="data/apartments.json",
        description="Path to the apartment definitions JSON file.",
    )
    tenants_json_path: str = Field(
        default="data/tenants.json",
        description="Path to the tenant definitions JSON file.",
    )
    transfers_json_path: str = Field(
        default="data/transfers.json",
        description="Path to the transfer records JSON file.",
    )
    bills_json_path: str = Field(
        default="data/bills.json",
        description="Path to the apartment bills JSON file.",
    )
    tenants_blacklist_json_path: str = Field(
        default="data/tenants_blacklist.json",
        description="Path to the blacklist entries JSON file.",
    )
    apartment_events_json_path: str = Field(
        default="data/apartment_events.json",
        description="Path to the apartment events JSON file.",
    )

    max_transfer_pln: float = Field(
        default=4500.0,
        description="Maximum accepted incoming transfer amount in PLN.",
    )
    max_refund_pln: float = Field(
        default=2500.0,
        description="Maximum accepted refund amount in PLN.",
    )


class Room(BaseModel):
    """Single room definition belonging to an apartment."""

    name: str = Field(description="Human-readable room name.")
    area_m2: float = Field(description="Room area measured in square meters.")


class Apartment(BaseModel):
    """Apartment definition with identity, location, and room structure."""

    key: str = Field(description="Unique apartment key used across datasets.")
    name: str = Field(description="Display name of the apartment.")
    location: str = Field(description="Address or location description.")
    area_m2: float = Field(description="Total apartment area in square meters.")
    rooms: dict[str, Room] = Field(
        description="Dictionary of rooms keyed by room identifier.",
    )

    @staticmethod
    def from_json_file(file_path: str) -> dict[str, "Apartment"]:
        """Load apartments from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing apartment data.

        Returns:
        -------
            dict[str, Apartment]: Apartments indexed by apartment key.

        Example:
        -------
            >>> apartments = Apartment.from_json_file("data/apartments.json")
            >>> "A1" in apartments
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, dict), "Expected a dictionary of apartments"
        return {key: Apartment(**apartment) for key, apartment in data.items()}


class Tenant(BaseModel):
    """Tenant definition used for settlements and agreement validation."""

    name: str = Field(description="Full tenant name.")
    apartment: str = Field(description="Apartment key assigned to the tenant.")
    room: str = Field(description="Room identifier occupied by the tenant.")
    rent_pln: float = Field(description="Monthly rent amount in PLN.")
    deposit_pln: float = Field(description="Required deposit amount in PLN.")
    date_agreement_from: str = Field(
        description="Agreement start date in ISO format YYYY-MM-DD.",
    )
    date_agreement_to: str = Field(
        description="Agreement end date in ISO format YYYY-MM-DD.",
    )

    @staticmethod
    def from_json_file(file_path: str) -> dict[str, "Tenant"]:
        """Load tenants from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing tenant data.

        Returns:
        -------
            dict[str, Tenant]: Tenants indexed by tenant identifier.

        Example:
        -------
            >>> tenants = Tenant.from_json_file("data/tenants.json")
            >>> isinstance(tenants, dict)
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, dict), "Expected a dictionary of tenants"
        return {key: Tenant(**tenant) for key, tenant in data.items()}


class TenantBlacklistEntry(BaseModel):
    """Blacklist record describing why a tenant is flagged."""

    tenant: str = Field(description="Tenant name present on the blacklist.")
    reason: str = Field(description="Reason for the blacklist entry.")

    @staticmethod
    def from_json_file(file_path: str) -> list["TenantBlacklistEntry"]:
        """Load tenant blacklist entries from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing blacklist data.

        Returns:
        -------
            list[TenantBlacklistEntry]: Parsed blacklist entries.

        Example:
        -------
            >>> entries = TenantBlacklistEntry.from_json_file(
            ...     "data/tenants_blacklist.json"
            ... )
            >>> isinstance(entries, list)
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, list), "Expected a list of blacklist entries"
        return [TenantBlacklistEntry(**entry) for entry in data]


class Transfer(BaseModel):
    """Financial transaction assigned to a tenant and optional settlement period."""

    amount_pln: float = Field(description="Transfer amount in PLN.")
    date: str = Field(description="Transaction date in ISO format YYYY-MM-DD.")
    settlement_year: int | None = Field(
        description="Year linked to the settlement, or None for unassigned transfers.",
    )
    settlement_month: int | None = Field(
        description="Month linked to the settlement, or None for unassigned transfers.",
    )
    tenant: str = Field(description="Tenant identifier referenced by the transfer.")
    type: str | None = Field(
        default=None,
        description="Optional transfer type, for example deposit.",
    )

    @staticmethod
    def from_json_file(file_path: str) -> list["Transfer"]:
        """Load transfers from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing transfer data.

        Returns:
        -------
            list[Transfer]: Parsed transfer records.

        Example:
        -------
            >>> transfers = Transfer.from_json_file("data/transfers.json")
            >>> isinstance(transfers, list)
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, list), "Expected a list of transfers"
        return [Transfer(**transfer) for transfer in data]


class Bill(BaseModel):
    """Financial obligation assigned to an apartment and settlement period."""

    amount_pln: float = Field(description="Bill amount in PLN.")
    date_due: str = Field(description="Bill due date in ISO format YYYY-MM-DD.")
    apartment: str = Field(description="Apartment key charged by the bill.")
    settlement_year: int = Field(description="Settlement year covered by the bill.")
    settlement_month: int = Field(description="Settlement month covered by the bill.")
    type: str = Field(description="Bill category, for example utilities or rent.")

    @staticmethod
    def from_json_file(file_path: str) -> list["Bill"]:
        """Load bills from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing bill data.

        Returns:
        -------
            list[Bill]: Parsed bill records.

        Example:
        -------
            >>> bills = Bill.from_json_file("data/bills.json")
            >>> isinstance(bills, list)
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, list), "Expected a list of bills"
        return [Bill(**bill) for bill in data]


class ApartmentSettlement(BaseModel):
    """Financial summary for an apartment in a selected month and year."""

    key: str = Field(description="Unique identifier of the settlement.")
    apartment: str = Field(description="Apartment key covered by the settlement.")
    month: int = Field(description="Settlement month.")
    year: int = Field(description="Settlement year.")
    total_due_pln: float = Field(description="Total amount due in PLN.")
    total_transfers_pln: float = Field(
        default=0.0,
        description="Total paid transfers assigned to the settlement in PLN.",
    )
    balance_pln: float = Field(
        default=0.0,
        description="Difference between transfers and dues in PLN.",
    )


class TenantSettlement(BaseModel):
    """Financial summary for a tenant in a selected month and year."""

    tenant: str = Field(description="Tenant name attached to the settlement.")
    apartment_settlement: str = Field(
        description="Identifier of the related apartment settlement.",
    )
    month: int = Field(description="Settlement month.")
    year: int = Field(description="Settlement year.")
    total_due_pln: float = Field(description="Tenant amount due in PLN.")
    total_transfers_pln: float = Field(
        default=0.0,
        description="Total paid transfers assigned to the tenant in PLN.",
    )
    balance_pln: float = Field(
        default=0.0,
        description="Difference between paid transfers and due amount in PLN.",
    )


class ApartmentEvent(BaseModel):
    """Event or issue related to an apartment, optionally linked to a cost."""

    date: str = Field(description="Event date in ISO format YYYY-MM-DD.")
    apartment: str = Field(description="Apartment key related to the event.")
    amount_pln: float | None = Field(
        default=None,
        description="Optional cost associated with the event in PLN.",
    )
    tenant: str | None = Field(
        default=None,
        description="Optional tenant name related to the event.",
    )
    description: str = Field(description="Human-readable event description.")
    solved: bool = Field(
        default=False,
        description="Whether the event has already been resolved.",
    )

    @staticmethod
    def from_json_file(file_path: str) -> list["ApartmentEvent"]:
        """Load apartment events from a JSON file.

        Args:
        ----
            file_path (str): Path to the JSON file containing apartment events.

        Returns:
        -------
            list[ApartmentEvent]: Parsed apartment events.

        Example:
        -------
            >>> events = ApartmentEvent.from_json_file("data/apartment_events.json")
            >>> isinstance(events, list)
            True

        """
        data = None
        with open(file_path, encoding="utf-8") as file:
            data = json.load(file)
        assert isinstance(data, list), "Expected a list of apartment events"
        return [ApartmentEvent(**event) for event in data]
