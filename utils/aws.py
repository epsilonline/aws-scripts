import boto3
import typer
from botocore.session import Session
from typing import Dict, Optional

Boto3Client = object


class AWSHelper:
    """
    A static helper class to manage a single boto3.Session and its clients.

    This class uses static methods and class attributes, so it never needs to be instantiated.
    The AWS profile should be set once using the `configure` method before first use.
    """
    # Attributi di classe per mantenere lo stato condiviso
    _session: Optional[Session] = None
    _clients: Dict[str, Boto3Client] = {}
    _profile: Optional[str] = None
    _initialized: bool = False

    @staticmethod
    def configure(profile: Optional[str] = None):
        """
        Configures the helper with a specific AWS profile.
        This method should be called once at the beginning of the application.

        Args:
            profile: The name of the AWS profile to use. If None, the default is used.
        """
        if AWSHelper._initialized:

            typer.secho(f"Warning: AWSHelper was already configured for profile '{AWSHelper._profile or 'default'}'. "
                        "Re-configuration is ignored.", fg=typer.colors.YELLOW)
            return

        # typer.secho(f"Configuring CLI for use profile: '{profile or 'default'}'")
        AWSHelper._profile = profile
        AWSHelper._initialized = True

    @staticmethod
    def get_session() -> Session:
        """
        Lazy-loads and returns the boto3 session using class attributes.
        """
        if not AWSHelper._initialized:
            # Auto-configura con il profilo di default se non è stato fatto esplicitamente
            AWSHelper.configure()

        if AWSHelper._session is None:
            AWSHelper._session = boto3.Session(profile_name=AWSHelper._profile)

        return AWSHelper._session

    @staticmethod
    def get_client(service_name: str) -> Boto3Client:
        """
        Lazy-loads and returns a specific service client from the class-level cache.

        Args:
            service_name: The name of the AWS service (e.g., 's3', 'ec2').

        Returns:
            A boto3 client for the requested service.
        """
        if service_name not in AWSHelper._clients:
            # typer.secho(f"Client for '{service_name}' not found, creating new client...", fg=typer.colors.GREEN)
            session = AWSHelper.get_session()
            AWSHelper._clients[service_name] = session.client(service_name)

        return AWSHelper._clients[service_name]