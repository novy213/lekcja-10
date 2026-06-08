"""Manager class for handling apartment management operations.

The module exposes the :class:`Manager` service, which loads JSON-backed domain
data and provides higher-level operations for validation, reporting, and
financial summaries.
"""

from datetime import datetime

from src.models import (
    Apartment,
    ApartmentEvent,
    ApartmentSettlement,
    Bill,
    Parameters,
    Tenant,
    TenantBlacklistEntry,
    TenantSettlement,
    Transfer,
)


class Manager:
    """Service object coordinating apartment settlement data and business rules.

    Attributes
    ----------
        parameters (Parameters): Runtime configuration with JSON file paths and
            validation limits.
        apartments (dict[str, Apartment]): Apartments indexed by apartment key.
        tenants (dict[str, Tenant]): Tenants indexed by tenant identifier.
        transfers (list[Transfer]): Financial transfers imported from JSON.
        bills (list[Bill]): Apartment bills used to compute costs and balances.
        tenants_blacklist (list[TenantBlacklistEntry]): Blacklist entries used
            to verify whether a tenant is flagged.
        apartment_events (list[ApartmentEvent]): Additional apartment events,
            such as issues or one-off costs.

    """

    def __init__(self, parameters: Parameters):
        """Initialize the manager and eagerly load core data sources.

        Args:
        ----
            parameters (Parameters): Configuration object pointing to data
                files and operational limits.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> isinstance(manager.apartments, dict)
            True

        """
        self.parameters = parameters

        self.apartments = {}
        self.tenants = {}
        self.transfers = []
        self.bills = []
        self.tenants_blacklist = []
        self.apartment_events = []

        self.load_data()

    def load_data(self):
        """Load the core JSON datasets referenced by the configuration.

        The method refreshes apartments, tenants, transfers, bills, and tenant
        blacklist entries from disk.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.load_data()
            >>> len(manager.tenants) >= 0
            True

        """
        self.apartments = Apartment.from_json_file(self.parameters.apartments_json_path)
        self.tenants = Tenant.from_json_file(self.parameters.tenants_json_path)
        self.transfers = Transfer.from_json_file(self.parameters.transfers_json_path)
        self.bills = Bill.from_json_file(self.parameters.bills_json_path)
        self.tenants_blacklist = TenantBlacklistEntry.from_json_file(
            self.parameters.tenants_blacklist_json_path,
        )

    def load_additional_data(self):
        """Load optional datasets that are not required for base calculations.

        Currently this method imports apartment events used by reporting
        methods.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.load_additional_data()
            >>> isinstance(manager.apartment_events, list)
            True

        """
        self.apartment_events = ApartmentEvent.from_json_file(
            self.parameters.apartment_events_json_path,
        )

    def generate_apartment_events_report(
        self,
        apartment_key: str,
        only_unsolved: bool = True,
    ) -> list[ApartmentEvent]:
        """Return apartment events assigned to a selected apartment.

        Args:
        ----
            apartment_key (str): Apartment identifier used to filter events.
            only_unsolved (bool): When ``True``, include only unresolved events.

        Returns:
        -------
            list[ApartmentEvent]: Matching events for the selected apartment.

        Raises:
        ------
            ValueError: If the apartment key does not exist.

        """
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return [
            event
            for event in self.apartment_events
            if event.apartment == apartment_key
            and (not event.solved or not only_unsolved)
        ]

    def check_tenants_apartment_keys(self) -> bool:
        """Verify that every tenant references an existing apartment.

        Returns
        -------
            bool: ``True`` when all tenant apartment keys are valid.

        """
        for tenant in self.tenants.values():
            if tenant.apartment not in self.apartments:
                return False
        return True

    def get_apartment(self, apartment_key: str) -> Apartment | None:
        """Return a single apartment by key.

        Args:
        ----
            apartment_key (str): Apartment identifier.

        Returns:
        -------
            Apartment | None: The apartment instance, or ``None`` when the key
            is unknown.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.get_apartment("A1") is None
            False

        """
        return self.apartments.get(apartment_key, None)

    def get_apartment_costs(
        self,
        apartment_key: str,
        year: int = None,
        month: int = None,
    ) -> float | None:
        """Calculate total billed costs for an apartment.

        Args:
        ----
            apartment_key (str): Apartment identifier.
            year (int | None): Optional settlement year filter.
            month (int | None): Optional settlement month filter.

        Returns:
        -------
            float | None: Total bill amount in PLN, or ``None`` if the
            apartment key is unknown.

        Raises:
        ------
            ValueError: If ``month`` is outside the ``1..12`` range.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.get_apartment_costs("A1", year=2023, month=1) >= 0
            True

        """
        if month is not None and (month < 1 or month > 12):
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = 0.0
        for bill in self.bills:
            if (
                bill.apartment == apartment_key
                and (year is None or bill.settlement_year == year)
                and (month is None or bill.settlement_month == month)
            ):
                total_cost += bill.amount_pln
        return total_cost

    def get_settlement(
        self,
        apartment_key: str,
        year: int,
        month: int,
    ) -> ApartmentSettlement | None:
        """Build an apartment-level settlement for a month.

        Args:
        ----
            apartment_key (str): Apartment identifier.
            year (int): Settlement year.
            month (int): Settlement month.

        Returns:
        -------
            ApartmentSettlement | None: Generated settlement object, or
            ``None`` if the apartment does not exist.

        Raises:
        ------
            ValueError: If ``month`` is outside the ``1..12`` range.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> settlement = manager.get_settlement("A1", year=2023, month=1)
            >>> settlement is not None
            True

        """
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            return None
        total_cost = self.get_apartment_costs(apartment_key, year, month)
        if total_cost is None:
            return None

        return ApartmentSettlement(
            key=f"{apartment_key}-{year}-{month}",
            apartment=apartment_key,
            year=year,
            month=month,
            total_due_pln=total_cost,
        )

    def create_tenants_settlements(
        self,
        apartment_settlement: ApartmentSettlement,
    ) -> list[TenantSettlement] | None:
        """Split an apartment settlement evenly across its tenants.

        Args:
        ----
            apartment_settlement (ApartmentSettlement): Apartment summary used
                as the source for tenant shares.

        Returns:
        -------
            list[TenantSettlement] | None: Tenant-level settlements, an empty
            list when no tenants are assigned, or ``None`` if the apartment is
            unknown.

        Raises:
        ------
            ValueError: If the settlement month is outside the ``1..12`` range.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> settlement = manager.get_settlement("A1", year=2023, month=1)
            >>> output = manager.create_tenants_settlements(settlement)
            >>> isinstance(output, list)
            True

        """
        if apartment_settlement.month < 1 or apartment_settlement.month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_settlement.apartment not in self.apartments:
            return None
        tenants_in_apartment = [
            tenant
            for tenant in self.tenants.values()
            if tenant.apartment == apartment_settlement.apartment
        ]
        if not tenants_in_apartment:
            return []

        return [
            TenantSettlement(
                tenant=tenant.name,
                apartment_settlement=apartment_settlement.key,
                month=apartment_settlement.month,
                year=apartment_settlement.year,
                total_due_pln=apartment_settlement.total_due_pln
                / len(tenants_in_apartment),
            )
            for tenant in tenants_in_apartment
        ]

    def get_debtors(self, apartment_key: str, year: int, month: int) -> list[str]:
        """Return tenant names whose payments do not cover the monthly share.

        Args:
        ----
            apartment_key (str): Apartment identifier.
            year (int): Settlement year.
            month (int): Settlement month.

        Returns:
        -------
            list[str]: Tenant names with insufficient payments for the period.

        Raises:
        ------
            ValueError: If ``month`` is outside the ``1..12`` range.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> debtors = manager.get_debtors("A1", year=2023, month=1)
            >>> isinstance(debtors, list)
            True

        """
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        output = []
        settlement = self.get_settlement(apartment_key, year, month)
        tenant_settlements = self.create_tenants_settlements(settlement)

        for tenant_settlement in tenant_settlements:
            tenant_transfers = [
                transfer
                for transfer in self.transfers
                if self.tenants[transfer.tenant].name == tenant_settlement.tenant
                and transfer.settlement_year == year
                and transfer.settlement_month == month
            ]
            total_paid = sum(
                transfer.amount_pln
                for transfer in tenant_transfers
                if transfer.settlement_year == year
                and transfer.settlement_month == month
            )
            if total_paid < tenant_settlement.total_due_pln:
                output.append(tenant_settlement.tenant)
        return output

    def calculate_tax(self, year: int, month: int, tax_rate: float) -> float:
        """Calculate tax from transfer income for a selected month.

        Args:
        ----
            year (int): Settlement year.
            month (int): Settlement month.
            tax_rate (float): Tax rate expressed as a decimal fraction.

        Returns:
        -------
            float: Rounded tax amount in PLN.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.calculate_tax(year=2023, month=1, tax_rate=0.085) >= 0
            True

        """
        total_income = sum(
            transfer.amount_pln
            for transfer in self.transfers
            if transfer.settlement_year == year and transfer.settlement_month == month
        )
        return round(total_income * tax_rate, 0)

    def check_deposits(self) -> float:
        """Compare collected tenant deposits with required deposit values.

        Returns
        -------
            float: Difference between paid deposits and expected deposits.
            Positive values mean overpayment, negative values mean shortage.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> isinstance(manager.check_deposits(), float)
            True

        """
        total_deposits = 0.0
        total_due = 0.0
        for _, tenant in self.tenants.items():
            total_deposits += sum(
                transfer.amount_pln
                for transfer in self.transfers
                if self.tenants[transfer.tenant].name == tenant.name
                and transfer.type == "deposit"
            )
            total_due += tenant.deposit_pln

        return total_deposits - total_due

    def get_annual_balance(self, year: int) -> float:
        """Calculate the annual balance for a selected year.

        Args:
        ----
            year (int): The year for which to calculate the balance.

        Returns:
        -------
            float: Annual balance computed as transfers minus bills.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> balance = manager.get_annual_balance(year=2023)
            >>> isinstance(balance, float)
            True

        """
        total_income = sum(
            transfer.amount_pln
            for transfer in self.transfers
            if transfer.settlement_year == year
        )
        total_due = sum(
            bill.amount_pln for bill in self.bills if bill.settlement_year == year
        )
        return total_income - total_due

    def has_any_bills(self, apartment_key: str, year: int, month: int) -> bool:
        """Check whether bills exist for an apartment and settlement period.

        Args:
        ----
            apartment_key (str): Apartment identifier.
            year (int): Settlement year.
            month (int): Settlement month.

        Returns:
        -------
            bool: ``True`` if at least one matching bill exists.

        Raises:
        ------
            ValueError: If ``month`` is invalid or the apartment key is unknown.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> manager.has_any_bills("A1", year=2023, month=1)
            True

        """
        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12")
        if apartment_key not in self.apartments:
            raise ValueError("Apartment key does not exist")
        return any(
            bill
            for bill in self.bills
            if bill.apartment == apartment_key
            and bill.settlement_year == year
            and bill.settlement_month == month
        )

    def check_transfers_amount_range(self) -> bool:
        """Validate transfer amounts against configured safety limits.

        Returns
        -------
            bool: ``True`` when every transfer amount is within the configured
            transfer and refund bounds.

        Example:
        -------
            >>> from src.models import Parameters
            >>> manager = Manager(Parameters())
            >>> isinstance(manager.check_transfers_amount_range(), bool)
            True

        """
        for transfer in self.transfers:
            if (
                transfer.amount_pln > self.parameters.max_transfer_pln
                or transfer.amount_pln < -self.parameters.max_refund_pln
            ):
                return False
        return True

    def check_tenant_blacklist(self, tenant_name: str) -> bool:
        """Check whether a tenant appears on the blacklist.

        Args:
        ----
            tenant_name (str): Human-readable tenant name.

        Returns:
        -------
            bool: ``True`` if the tenant is blacklisted.

        """
        return any(
            entry for entry in self.tenants_blacklist if entry.tenant == tenant_name
        )

    def check_transfers_tenant(self) -> bool:
        """Validate transfer ownership and agreement date consistency.

        Returns
        -------
            bool: ``True`` when every transfer references an existing tenant and
            falls within the tenant agreement period.

        """
        for transfer in self.transfers:
            if transfer.tenant not in self.tenants:
                return False
            if (
                transfer.settlement_year is not None
                and transfer.settlement_month is not None
            ):
                agreement_from = self.tenants[transfer.tenant].date_agreement_from
                agreement_from = datetime.strptime(agreement_from, "%Y-%m-%d").date()
                agreement_to = self.tenants[transfer.tenant].date_agreement_to
                agreement_to = datetime.strptime(agreement_to, "%Y-%m-%d").date()
                if (transfer.settlement_year < agreement_from.year) or (
                    transfer.settlement_year > agreement_to.year
                ):
                    return False

        return True
