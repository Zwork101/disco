import six
import warnings

from disco.api.http import APIException
from disco.util.paginator import Paginator
from disco.util.snowflake import to_snowflake
from disco.types.base import (
    SlottedModel, Field, ListField, AutoDictField, DictField, snowflake, text, enum, datetime,
    cached_property,
)
from disco.types.user import User
from disco.types.voice import VoiceState
from disco.types.channel import Channel, ChannelType
from disco.types.message import Emoji
from disco.types.permissions import PermissionValue, Permissions, Permissible


class VerificationLevel(object):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    EXTREME = 4


class ExplicitContentFilterLevel(object):
    NONE = 0
    WITHOUT_ROLES = 1
    ALL = 2


class DefaultMessageNotificationsLevel(object):
    ALL_MESSAGES = 0
    ONLY_MENTIONS = 1


class GuildEmoji(Emoji):
    """
    An emoji object.

    If the id is none, then this is a normal Unicode emoji, otherwise it's a custom discord emoji.

    Attributes
    ----------
    id : snowflake or None
        The ID of this emoji.
    name : str
        The name of this emoji.
    guild_id : snowflake
        The snowflake of the guild this emoji belongs too (Not available for unicode emojis)
    require_colons : bool
        Whether this emoji requires colons to use. (Not available for unicode emojis)
    managed : bool
        Whether this emoji is managed by an integration. (Not available for unicode emojis)
    roles : list(snowflake)
        Roles this emoji is attached to. (Not available for unicode emojis)
    animated : bool
        Whether this emoji is animated. (Not available for unicode emojis)
    url : str
        A url to the image of this emoji. (Not available for unicode emojis)
    guild : :class:`~disco.types.guild.Guild`
        The guild this emoji belongs too (Not available for unicode emojis)
    """
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    require_colons = Field(bool)
    managed = Field(bool)
    roles = ListField(snowflake)
    animated = Field(bool)
    available = Field(bool)

    def __str__(self):
        return u'<{}:{}:{}>'.format('a' if self.animated else '', self.name, self.id)

    def update(self, **kwargs):
        """
        Update emoji settings

        Update the settings for this non-unicode emoji

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_emojis_modify`
        """
        return self.client.api.guilds_emojis_modify(self.guild_id, self.id, **kwargs)

    def delete(self, **kwargs):
        """
        Delete emoji

        Remove this non-unicode emoji from the guild

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_emojis_delete`
        """
        return self.client.api.guilds_emojis_delete(self.guild_id, self.id, **kwargs)

    @property
    def url(self):
        return 'https://cdn.discordapp.com/emojis/{}.{}'.format(self.id, 'gif' if self.animated else 'png')

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)


class PruneCount(SlottedModel):
    """
    Amount of people getting pruned

    Attributes
    ----------
    pruned : int or None
        The amount of people getting pruned if applicable
    """
    pruned = Field(int, default=None)


class Role(SlottedModel):
    """
    A role object.

    Discord guild role. Roles can be used to seperate users on the member list,
    color people's names and give people permissions.

    Attributes
    ----------
    id : snowflake
        The role ID.
    name : string
        The role name.
    hoist : bool
        Whether this role is hoisted (displayed separately in the sidebar).
    managed : bool
        Whether this role is managed by an integration.
    color : int
        The RGB color of this role.
    permissions : :class:`disco.types.permissions.PermissionsValue`
        The permissions this role grants.
    position : int
        The position of this role in the hierarchy.
    mentionable : bool
        Whether this role can be mentioned by anyone
    mention : str
        A string mentioning the role
    guild : :class:`~disco.types.guild.Guild`
        The guild this emoji belongs too
    """
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    hoist = Field(bool)
    managed = Field(bool)
    color = Field(int)
    permissions = Field(PermissionValue)
    position = Field(int)
    mentionable = Field(bool)

    def __str__(self):
        return self.name

    def delete(self, **kwargs):
        """
        Delete role

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.guild.Guild.delete_role`
        """
        self.guild.delete_role(self, **kwargs)

    def update(self, *args, **kwargs):
        """
        Update role

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.types.guild.Guild.update_role`
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.guild.Guild.update_role`
        """
        self.guild.update_role(self, *args, **kwargs)

    @property
    def mention(self):
        return '<@&{}>'.format(self.id)

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)


class GuildBan(SlottedModel):
    """
    Guild ban

    Attributes
    ----------
    user : :class:`~disco.types.user.User`
        The user that was banned
    reason : str
        The reason they were banned
    """
    user = Field(User)
    reason = Field(text)


class GuildEmbed(SlottedModel):
    """
    Guild embed

    Attributes
    ----------
    enabled : bool
        If the guild has it's embed enabled
    channel_id : snowflake
        The channel that's displayed on the guild embed
    """
    enabled = Field(bool)
    channel_id = Field(snowflake)


class GuildMember(SlottedModel):
    """
    A guild member

    Guild members are essentially wrappers on user that depend on the guild.
    this includes information like nick names, roles, etc.

    Attributes
    ----------
    id : snowflake
        The id of the user
    user : :class:`~disco.types.user.User`
        The user object of this member.
    guild_id : snowflake
        The guild this member is part of.
    nick : str
        The nickname of the member.
    name : str
        The name of the member (the nickname if they have one, elsewise they're username)
    mute : bool
        Whether this member is server voice-muted.
    deaf : bool
        Whether this member is server voice-deafened.
    joined_at : datetime
        When this user joined the guild.
    roles : list of snowflake
        Roles this member is part of.
    premium_since : datetime
        When this user set their Nitro boost to this server.
    owner : bool
        If this member is the owner of the guild
    mention : str
        A string that mentions the member (different than user mention if they have nick)
    guild : :class:`~disco.types.guild.Guild`
        The guild this member belongs too
    permissions : :class:`disco.types.permissions.PermissionValue`
        The permissions the user has on this guild, ignoring channel overwrites
    """
    user = Field(User)
    guild_id = Field(snowflake)
    nick = Field(text)
    mute = Field(bool)
    deaf = Field(bool)
    joined_at = Field(datetime)
    roles = ListField(snowflake)
    premium_since = Field(datetime)

    def __str__(self):
        return self.user.__str__()

    @property
    def name(self):
        return self.nick or self.user.username

    def get_voice_state(self):
        """
        Get current voice state

        Returns
        -------
        :class:`disco.types.voice.VoiceState` or None
            Returns the voice state for the member if they are currently connected
            to the guild's voice server.
        """
        return self.guild.get_voice_state(self)

    def kick(self, **kwargs):
        """
        Kicks the member from the guild.

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_members_kick`

        """
        self.client.api.guilds_members_kick(self.guild.id, self.user.id, **kwargs)

    def ban(self, delete_message_days=0, **kwargs):
        """
        Bans the member from the guild.

        Parameters
        ----------
        delete_message_days : int
            The number of days to retroactively delete messages for.
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.guild.Guild.create_ban`
        """
        self.guild.create_ban(self, delete_message_days, **kwargs)

    def unban(self, **kwargs):
        """
        Unbans a member from the guild.

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.guild.Guild.delete_ban`
        """
        self.guild.delete_ban(self, **kwargs)

    def set_nickname(self, nickname=None, **kwargs):
        """
        Sets the member's nickname

        Set's a guild member's username. If the nicname provided is None, their name will be reset.
        This same method can be used if the guild member is the bot.

        Parameters
        ----------
        nickname : str or None
            The nickname (or none to reset) to set.
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_members_modify`.
        """
        if self.client.state.me.id == self.user.id:
            self.client.api.guilds_members_me_nick(self.guild.id, nick=nickname or '', **kwargs)
        else:
            self.client.api.guilds_members_modify(self.guild.id, self.user.id, nick=nickname or '', **kwargs)

    def disconnect(self):
        """
        Disconnects the member from voice.

        Removes this member from their choice channel, does nothing if they're not in a voice channel
        """
        self.modify(channel_id=None)

    def modify(self, **kwargs):
        """
        Modify this guild member

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_members_modify`.
        """
        self.client.api.guilds_members_modify(self.guild.id, self.user.id, **kwargs)

    def add_role(self, role, **kwargs):
        """
        Add role to this guild member

        Parameters
        ----------
        role : :class:`~disco.types.guild.Role` or snowflake
            The role to add to this member
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_members_roles_add`.
        """
        self.client.api.guilds_members_roles_add(self.guild.id, self.user.id, to_snowflake(role), **kwargs)

    def remove_role(self, role, **kwargs):
        """
        Remove role to this guild member

        Parameters
        ----------
        role : :class:`~disco.types.guild.Role` or snowflake
            The role to remove from this member
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.guilds_members_roles_remove`.
        """
        self.client.api.guilds_members_roles_remove(self.guild.id, self.user.id, to_snowflake(role), **kwargs)

    @cached_property
    def owner(self):
        return self.guild.owner_id == self.id

    @cached_property
    def mention(self):
        if self.nick:
            return '<@!{}>'.format(self.id)
        return self.user.mention

    @property
    def id(self):
        return self.user.id

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def permissions(self):
        return self.guild.get_permissions(self)


class Guild(SlottedModel, Permissible):
    """
    A guild object.

    Discord guilds are the parent to almost all discord objects, with the exception of DMs.

    Attributes
    ----------
    id : snowflake
        The id of this guild.
    owner_id : snowflake
        The id of the owner.
    owner : :class:~disco.types.guild.GuildMember`
        The owner as a member
    afk_channel_id : snowflake
        The id of the afk channel.
    embed_channel_id : snowflake
        The id of the embed channel.
    system_channel_id : snowflake
        The id of the system channel.
    name : str
        Guild's name.
    icon : str
        Guild's icon image hash
    splash : str
        Guild's splash image hash
    banner : str
        Guild's banner image hash
    region : str
        Voice region.
    afk_timeout : int
        Delay after which users are automatically moved to the afk channel.
    embed_enabled : bool
        Whether the guild's embed is enabled.
    verification_level : int
        The verification level used by the guild.
    mfa_level : int
        The MFA level used by the guild.
    features : list of str
        Extra features enabled for this guild.
    members : dict of snowflake to :class:`~disco.types.guild.GuildMember`
        All of the guild's members.
    channels : dict of snowflake to :class:`~disco.types.channel.Channel`
        All of the guild's channels.
    roles : dict of snowflake to :class:`~disco.types.guild.Role`
        All of the guild's roles.
    emojis : dict of snowflake to :class:`~disco.types.guild.GuildEmoji`
        All of the guild's emojis.
    voice_states : dict of str to :class:`~disco.types.voice.VoiceState`
        All of the guild's voice states.
    premium_tier : int
        Guild's premium tier.
    premium_subscription_count : int
        The amount of users using their Nitro boost on this guild.
    """
    id = Field(snowflake)
    owner_id = Field(snowflake)
    afk_channel_id = Field(snowflake)
    embed_channel_id = Field(snowflake)
    system_channel_id = Field(snowflake)
    name = Field(text)
    icon = Field(text)
    splash = Field(text)
    banner = Field(text)
    region = Field(text)
    afk_timeout = Field(int)
    embed_enabled = Field(bool)
    verification_level = Field(enum(VerificationLevel))
    explicit_content_filter = Field(enum(ExplicitContentFilterLevel))
    default_message_notifications = Field(enum(DefaultMessageNotificationsLevel))
    mfa_level = Field(int)
    features = ListField(str)
    members = AutoDictField(GuildMember, 'id')
    channels = AutoDictField(Channel, 'id')
    roles = AutoDictField(Role, 'id')
    emojis = AutoDictField(GuildEmoji, 'id')
    voice_states = AutoDictField(VoiceState, 'session_id')
    member_count = Field(int)
    premium_tier = Field(int)
    premium_subscription_count = Field(int, default=0)
    vanity_url_code = Field(text)
    max_presences = Field(int, default=5000)
    max_members = Field(int)
    description = Field(text)

    def __init__(self, *args, **kwargs):
        super(Guild, self).__init__(*args, **kwargs)

        self.attach(six.itervalues(self.channels), {'guild_id': self.id})
        self.attach(six.itervalues(self.members), {'guild_id': self.id})
        self.attach(six.itervalues(self.roles), {'guild_id': self.id})
        self.attach(six.itervalues(self.emojis), {'guild_id': self.id})
        self.attach(six.itervalues(self.voice_states), {'guild_id': self.id})

    @cached_property
    def owner(self):
        return self.members.get(self.owner_id)

    def get_permissions(self, member):
        """
        Get the permissions a user has in this guild.

        Parameters
        ----------
        member : :class:`~disco.types.guild.GuildMember` or snowflake
            Member to get the permissions for

        Returns
        -------
        :class:`~disco.types.permissions.PermissionValue`
            Computed permission value for the user.
        """
        if not isinstance(member, GuildMember):
            member = self.get_member(member)

        # Owner has all permissions
        if self.owner_id == member.id:
            return PermissionValue(Permissions.ADMINISTRATOR)

        # Our value starts with the guilds default (@everyone) role permissions
        value = PermissionValue(self.roles.get(self.id).permissions)

        # Iterate over all roles the user has (plus the @everyone role)
        for role in map(self.roles.get, member.roles + [self.id]):
            value += role.permissions

        return value

    def get_voice_state(self, user):
        """
        Get voice state

        Attempt to get a voice state for a given user (who should be a member of
        this guild).

        Parameters
        ----------
        user : :class:`~disco.types.guild.GuildMember` or snowflake
            The guild member to get the voice state of


        Returns
        -------
        :class:`~disco.types.voice.VoiceState`
            The voice state for the user in this guild.
        """
        user = to_snowflake(user)

        for state in six.itervalues(self.voice_states):
            if state.user_id == user:
                return state

    def get_member(self, user):
        """
        Attempt to get a member from a given user.

        Parameters
        ----------
        user : :class:`~disco.types.user.User` or snowflake
            The user to get member status of

        Returns
        -------
        :class:`~disco.types.guild.GuildMember`
            The guild member object for the given user.
        """
        user = to_snowflake(user)

        if user not in self.members:
            try:
                self.members[user] = self.client.api.guilds_members_get(self.id, user)
            except APIException:
                return

        return self.members.get(user)

    def get_prune_count(self, days=None):
        return self.client.api.guilds_prune_count_get(self.id, days=days)

    def prune(self, days=None, compute_prune_count=None):
        return self.client.api.guilds_prune_create(self.id, days=days, compute_prune_count=compute_prune_count)

    def create_role(self, **kwargs):
        """
        Create a new role.

        Returns
        -------
        :class:`Role`
            The newly created role.
        """
        return self.client.api.guilds_roles_create(self.id, **kwargs)

    def delete_role(self, role, **kwargs):
        """
        Delete a role.
        """
        self.client.api.guilds_roles_delete(self.id, to_snowflake(role), **kwargs)

    def update_role(self, role, **kwargs):
        if 'permissions' in kwargs and isinstance(kwargs['permissions'], PermissionValue):
            kwargs['permissions'] = kwargs['permissions'].value

        return self.client.api.guilds_roles_modify(self.id, to_snowflake(role), **kwargs)

    def request_guild_members(self, query=None, limit=0, presences=False):
        self.client.gw.request_guild_members(self.id, query, limit, presences)

    def request_guild_members_by_id(self, user_id_or_ids, limit=0, presences=False):
        self.client.gw.request_guild_members_by_id(self.id, user_id_or_ids, limit, presences)

    def sync(self):
        warnings.warn(
            'Guild.sync has been deprecated in place of Guild.request_guild_members',
            DeprecationWarning)

        self.request_guild_members()

    def get_bans(self):
        return self.client.api.guilds_bans_list(self.id)

    def get_ban(self, user):
        return self.client.api.guilds_bans_get(self.id, user)

    def delete_ban(self, user, **kwargs):
        self.client.api.guilds_bans_delete(self.id, to_snowflake(user), **kwargs)

    def create_ban(self, user, *args, **kwargs):
        self.client.api.guilds_bans_create(self.id, to_snowflake(user), *args, **kwargs)

    def create_channel(self, *args, **kwargs):
        warnings.warn(
            'Guild.create_channel will be deprecated soon, please use:'
            ' Guild.create_text_channel or Guild.create_category or Guild.create_voice_channel',
            DeprecationWarning)

        return self.client.api.guilds_channels_create(self.id, *args, **kwargs)

    def create_category(self, name, permission_overwrites=[], position=None, reason=None):
        """
        Creates a category within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_CATEGORY, name=name, permission_overwrites=permission_overwrites,
            position=position, reason=reason,
        )

    def create_text_channel(
            self,
            name,
            permission_overwrites=[],
            parent_id=None,
            nsfw=None,
            position=None,
            reason=None):
        """
        Creates a text channel within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_TEXT, name=name, permission_overwrites=permission_overwrites,
            parent_id=parent_id, nsfw=nsfw, position=position, reason=reason,
        )

    def create_voice_channel(
            self,
            name,
            permission_overwrites=[],
            parent_id=None,
            bitrate=None,
            user_limit=None,
            position=None,
            reason=None):
        """
        Creates a voice channel within the guild.
        """
        return self.client.api.guilds_channels_create(
            self.id, ChannelType.GUILD_VOICE, name=name, permission_overwrites=permission_overwrites,
            parent_id=parent_id, bitrate=bitrate, user_limit=user_limit, position=position, reason=None)

    def leave(self):
        return self.client.api.users_me_guilds_delete(self.id)

    def get_invites(self):
        return self.client.api.guilds_invites_list(self.id)

    def get_emojis(self):
        return self.client.api.guilds_emojis_list(self.id)

    def get_emoji(self, emoji):
        return self.client.api.guilds_emojis_get(self.id, emoji)

    def get_voice_regions(self):
        return self.client.api.guilds_voice_regions_list(self.id)

    def get_icon_url(self, still_format='webp', animated_format='gif', size=1024):
        if not self.icon:
            return ''

        if self.icon.startswith('a_'):
            return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(
                self.id, self.icon, animated_format, size
            )
        else:
            return 'https://cdn.discordapp.com/icons/{}/{}.{}?size={}'.format(
                self.id, self.icon, still_format, size
            )

    def get_vanity_url(self):
        if not self.vanity_url_code:
            return ''

        return 'https://discord.gg/' + self.vanity_url_code

    def get_splash_url(self, fmt='webp', size=1024):
        if not self.splash:
            return ''

        return 'https://cdn.discordapp.com/splashes/{}/{}.{}?size={}'.format(self.id, self.splash, fmt, size)

    def get_banner_url(self, fmt='webp', size=1024):
        if not self.banner:
            return ''

        return 'https://cdn.discordapp.com/banners/{}/{}.{}?size={}'.format(self.id, self.banner, fmt, size)

    @property
    def icon_url(self):
        return self.get_icon_url()

    @property
    def vanity_url(self):
        return self.get_vanity_url()

    @property
    def splash_url(self):
        return self.get_splash_url()

    @property
    def banner_url(self):
        return self.get_banner_url()

    @property
    def system_channel(self):
        return self.channels.get(self.system_channel_id)

    @property
    def audit_log(self):
        return self.audit_log_iter()

    def audit_log_iter(self, **kwargs):
        return Paginator(
            self.client.api.guilds_auditlogs_list,
            'before',
            self.id,
            **kwargs
        )

    def get_audit_log_entries(self, *args, **kwargs):
        return self.client.api.guilds_auditlogs_list(self.id, *args, **kwargs)


class IntegrationAccount(SlottedModel):
    id = Field(text)
    name = Field(text)


class Integration(SlottedModel):
    id = Field(snowflake)
    name = Field(text)
    type = Field(text)
    enabled = Field(bool)
    syncing = Field(bool)
    role_id = Field(snowflake)
    expire_behavior = Field(int)
    expire_grace_period = Field(int)
    user = Field(User)
    account = Field(IntegrationAccount)
    synced_at = Field(datetime)


class AuditLogActionTypes(object):
    GUILD_UPDATE = 1
    CHANNEL_CREATE = 10
    CHANNEL_UPDATE = 11
    CHANNEL_DELETE = 12
    CHANNEL_OVERWRITE_CREATE = 13
    CHANNEL_OVERWRITE_UPDATE = 14
    CHANNEL_OVERWRITE_DELETE = 15
    MEMBER_KICK = 20
    MEMBER_PRUNE = 21
    MEMBER_BAN_ADD = 22
    MEMBER_BAN_REMOVE = 23
    MEMBER_UPDATE = 24
    MEMBER_ROLE_UPDATE = 25
    ROLE_CREATE = 30
    ROLE_UPDATE = 31
    ROLE_DELETE = 32
    INVITE_CREATE = 40
    INVITE_UPDATE = 41
    INVITE_DELETE = 42
    WEBHOOK_CREATE = 50
    WEBHOOK_UPDATE = 51
    WEBHOOK_DELETE = 52
    EMOJI_CREATE = 60
    EMOJI_UPDATE = 61
    EMOJI_DELETE = 62
    MESSAGE_DELETE = 72


GUILD_ACTIONS = (
    AuditLogActionTypes.GUILD_UPDATE,
)

CHANNEL_ACTIONS = (
    AuditLogActionTypes.CHANNEL_CREATE,
    AuditLogActionTypes.CHANNEL_UPDATE,
    AuditLogActionTypes.CHANNEL_DELETE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_CREATE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_UPDATE,
    AuditLogActionTypes.CHANNEL_OVERWRITE_DELETE,
)

MEMBER_ACTIONS = (
    AuditLogActionTypes.MEMBER_KICK,
    AuditLogActionTypes.MEMBER_PRUNE,
    AuditLogActionTypes.MEMBER_BAN_ADD,
    AuditLogActionTypes.MEMBER_BAN_REMOVE,
    AuditLogActionTypes.MEMBER_UPDATE,
    AuditLogActionTypes.MEMBER_ROLE_UPDATE,
)

ROLE_ACTIONS = (
    AuditLogActionTypes.ROLE_CREATE,
    AuditLogActionTypes.ROLE_UPDATE,
    AuditLogActionTypes.ROLE_DELETE,
)

INVITE_ACTIONS = (
    AuditLogActionTypes.INVITE_CREATE,
    AuditLogActionTypes.INVITE_UPDATE,
    AuditLogActionTypes.INVITE_DELETE,
)

WEBHOOK_ACTIONS = (
    AuditLogActionTypes.WEBHOOK_CREATE,
    AuditLogActionTypes.WEBHOOK_UPDATE,
    AuditLogActionTypes.WEBHOOK_DELETE,
)

EMOJI_ACTIONS = (
    AuditLogActionTypes.EMOJI_CREATE,
    AuditLogActionTypes.EMOJI_UPDATE,
    AuditLogActionTypes.EMOJI_DELETE,
)

MESSAGE_ACTIONS = (
    AuditLogActionTypes.MESSAGE_DELETE,
)


class AuditLogObjectChange(SlottedModel):
    key = Field(text)
    new_value = Field(text)
    old_value = Field(text)


class AuditLogEntry(SlottedModel):
    id = Field(snowflake)
    guild_id = Field(snowflake)
    user_id = Field(snowflake)
    target_id = Field(snowflake)
    action_type = Field(enum(AuditLogActionTypes))
    changes = ListField(AuditLogObjectChange)
    options = DictField(text, text)
    reason = Field(text)

    _cached_target = Field(None)

    @classmethod
    def create(cls, client, users, webhooks, data, **kwargs):
        self = super(SlottedModel, cls).create(client, data, **kwargs)

        if self.action_type in MEMBER_ACTIONS:
            self._cached_target = users[self.target_id]
        elif self.action_type in WEBHOOK_ACTIONS:
            self._cached_target = webhooks[self.target_id]

        return self

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def user(self):
        return self.client.state.users.get(self.user_id)

    @cached_property
    def target(self):
        if self.action_type in GUILD_ACTIONS:
            return self.guild
        elif self.action_type in CHANNEL_ACTIONS:
            return self.guild.channels.get(self.target_id)
        elif self.action_type in MEMBER_ACTIONS:
            return self._cached_target or self.state.users.get(self.target_id)
        elif self.action_type in ROLE_ACTIONS:
            return self.guild.roles.get(self.target_id)
        elif self.action_type in WEBHOOK_ACTIONS:
            return self._cached_target
        elif self.action_type in EMOJI_ACTIONS:
            return self.guild.emojis.get(self.target_id)
