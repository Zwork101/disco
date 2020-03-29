import re
import six

from six.moves import map

from disco.util.snowflake import to_snowflake
from disco.util.functional import one_or_many, chunks
from disco.types.user import User
from disco.types.base import SlottedModel, Field, AutoDictField, snowflake, enum, text, cached_property
from disco.types.permissions import Permissions, Permissible, PermissionValue


NSFW_RE = re.compile('^nsfw(-|$)')


class ChannelType(object):
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_NEWS = 5
    GUILD_STORE = 6


class PermissionOverwriteType(object):
    ROLE = 'role'
    MEMBER = 'member'


class ChannelSubType(SlottedModel):
    channel_id = Field(None)

    @cached_property
    def channel(self):
        return self.client.state.channels.get(self.channel_id)


class PermissionOverwrite(ChannelSubType):
    """
    A PermissionOverwrite for a :class:`Channel`.

    Attributes
    ----------
    id : snowflake
        The overwrite ID.
    type : :const:`~disco.types.channel.PermissionsOverwriteType`
        The overwrite type.
    allow : :class:`~disco.types.permissions.PermissionValue`
        All allowed permissions.
    deny : :class:`~disco.types.permissions.PermissionValue`
        All denied permissions.
    compiled : :class:`~disco.types.permissions.PermissionValue`
        All permissions, both allowed and denied
    """
    id = Field(snowflake)
    type = Field(enum(PermissionOverwriteType))
    allow = Field(PermissionValue, cast=int)
    deny = Field(PermissionValue, cast=int)

    channel_id = Field(snowflake)

    @classmethod
    def create_for_channel(cls, channel, entity, allow=0, deny=0):
        """"
        Creates a permission overwrite

        Generates a permission overwrite for a channel given the entity and the permission bitsets provided.

        Parameters
        ---------
        channel : :class:`~disco.types.channel.Channel`
            Channel to apply permission overwrite too
        entity : :class:`~disco.types.guild.Role` or :class:`~disco.types.guild.GuildMember`
            The role or member to provide or deny permissions too
        allow : :class:`~disco.types.permissions.Permissions`, optional
            Permissions to allow the role or user for the channel
        deny : :class:`~disco.types.permissions.Permissions` optional
            Permissions to deny the role or user for the channel

        Returns
        -------
        :class:`~disco.types.channel.PermissionOverwrite`
            An instance of the overwrite that was created
        """
        from disco.types.guild import Role

        ptype = PermissionOverwriteType.ROLE if isinstance(entity, Role) else PermissionOverwriteType.MEMBER
        return cls(
            client=channel.client,
            id=entity.id,
            type=ptype,
            allow=allow,
            deny=deny,
            channel_id=channel.id,
        ).save()

    @property
    def compiled(self):
        value = PermissionValue()
        value -= self.deny
        value += self.allow
        return value

    def save(self, **kwargs):
        """
        Send discord the permission overwrite

        This method is used if you created a permission overwrite without uploading it.
        For most use cases, use the create_for_channel classmethod instead.

        Parameters
        ----------
        kwargs
            Extra arguments to provide channels_permissions_modify

        Returns
        -------
        :class:`~disco.types.channel.PermissionOverwrite`
            Returns itself, no changes made
        """
        self.client.api.channels_permissions_modify(self.channel_id,
                                                    self.id,
                                                    self.allow.value or 0,
                                                    self.deny.value or 0,
                                                    self.type,
                                                    **kwargs)
        return self

    def delete(self, **kwargs):
        """
        Delete permission overwrite

        Removes the permission overwrite instance from it's channel. You can reverse the change with the save method.

        Parameters
        ----------
        kwargs
            Extra arguments to provide channels_permissions_delete
        """
        self.client.api.channels_permissions_delete(self.channel_id, self.id, **kwargs)


class Channel(SlottedModel, Permissible):
    """
    Represents a Discord Channel.

    Attributes
    ----------
    id : snowflake
        The channel ID.
    guild_id : snowflake, optional
        The guild id the channel is part of.
    name : str
        The channel's name.
    topic : str
        The channel's topic.
    position : int
        The channel's position.
    bitrate : int
        The channel's bitrate.
    user_limit : int
        The channel's user limit.
    recipients : list of :class:`~disco.types.user.User`
        Members of the channel (if the is a DM channel).
    type : :const:`~disco.types.channel.ChannelType`
        The type of the channel.
    overwrites : dict of snowflake to :class:`~disco.types.channel.PermissionOverwrite`
        Channel permissions overwrites.
    mention : str
        The channel's mention
    guild : :class:`~disco.types.guild.Guild`, optional
        Guild the channel belongs to (or None if not applicable).
    """
    id = Field(snowflake)
    guild_id = Field(snowflake)
    name = Field(text)
    topic = Field(text)
    last_message_id = Field(snowflake)
    position = Field(int)
    bitrate = Field(int)
    user_limit = Field(int)
    recipients = AutoDictField(User, 'id')
    nsfw = Field(bool)
    type = Field(enum(ChannelType))
    overwrites = AutoDictField(PermissionOverwrite, 'id', alias='permission_overwrites')
    parent_id = Field(snowflake)
    rate_limit_per_user = Field(int)

    def __init__(self, *args, **kwargs):
        super(Channel, self).__init__(*args, **kwargs)
        self.after_load()

    def after_load(self):
        # TODO: hackfix
        self.attach(six.itervalues(self.overwrites), {'channel_id': self.id, 'channel': self})

    def __str__(self):
        return u'#{}'.format(self.name) if self.name else six.text_type(self.id)

    def __repr__(self):
        return u'<Channel {} ({})>'.format(self.id, self)

    def get_permissions(self, user):
        """
        Get the permissions a user has in the channel.

        This method will first apply the user's permissions based on their roles and / or if they're the owner.
        It will then overwrite those permissions with the channel's permission overwrites.
        If the channel is a DM, the user is considered an administrator.

        Parameters
        ----------
        user : :class:`~disco.types.user.User` or :class:`~disco.types.guild.GuildMember`
            A user-like instance of the ID of a user to get the permissions for

        Returns
        -------
        :class:`~disco.types.permissions.PermissionValue`
            Computed permission value for the user.
        """
        if not self.guild_id:
            return Permissions.ADMINISTRATOR

        member = self.guild.get_member(user)
        base = self.guild.get_permissions(member)

        # First grab and apply the everyone overwrite
        everyone = self.overwrites.get(self.guild_id)
        if everyone:
            base -= everyone.deny
            base += everyone.allow

        for role_id in member.roles:
            overwrite = self.overwrites.get(role_id)
            if overwrite:
                base -= overwrite.deny
                base += overwrite.allow

        ow_member = self.overwrites.get(member.user.id)
        if ow_member:
            base -= ow_member.deny
            base += ow_member.allow

        return base

    @property
    def mention(self):
        return '<#{}>'.format(self.id)

    @property
    def is_guild(self):
        """
        Whether the channel belongs to a guild.
        """
        return self.type in (
            ChannelType.GUILD_TEXT,
            ChannelType.GUILD_VOICE,
            ChannelType.GUILD_CATEGORY,
            ChannelType.GUILD_NEWS,
        )

    @property
    def is_news(self):
        """
        Whether the channel contains news for the guild (used for verified guilds
        to produce activity feed news).
        """
        return self.type == ChannelType.GUILD_NEWS

    @property
    def is_dm(self):
        """
        Whether the channel is a DM (does not belong to a guild).
        """
        return self.type in (ChannelType.DM, ChannelType.GROUP_DM)

    @property
    def is_nsfw(self):
        """
        Whether the channel is an NSFW channel.
        """
        return bool(self.type == ChannelType.GUILD_TEXT and (self.nsfw or NSFW_RE.match(self.name)))

    @property
    def is_voice(self):
        """
        Whether the channel supports voice.
        """
        return self.type in (ChannelType.GUILD_VOICE, ChannelType.GROUP_DM)

    @property
    def messages(self):
        """
        A default :class:`~disco.types.channel.MessageIterator` for the channel, can be used to quickly and
        easily iterate over the channels entire message history. For more control,
        use :func:`~disco.types.channel.Channel.messages_iter`.
        """
        return self.messages_iter()

    @cached_property
    def guild(self):
        return self.client.state.guilds.get(self.guild_id)

    @cached_property
    def parent(self):
        """
        Parent the channel belongs to (or None if not applicable).
        """
        return self.guild.channels.get(self.parent_id)

    def messages_iter(self, **kwargs):
        """
        Creates message iterator

        Creates a new :class:`~disco.types.channel.MessageIterator` for the channel with the given keyword
        arguments.

        Parameters
        ----------
        kwargs
            Extra arguments to be passed into :class:`~disco.types.channel.MessageIterator`
        """
        return MessageIterator(self.client, self, **kwargs)

    def get_message(self, message):
        """
        Attempts to fetch and return a `Message` from the message object
        or id.

        Arguments
        ---------
        message : :class:`~disco.types.message.Message` or snowflake

        Returns
        -------
        :class:`~disco.types.message.Message`
            The fetched message.
        """
        return self.client.api.channels_messages_get(self.id, to_snowflake(message))

    def get_invites(self):
        """
        Finds invites for the channel

        Invites are not global for a server like they used to be, and now must be created for specific channels.
        This method finds all the invites that use the channel as the landing page.

        Returns
        -------
        list of :class:`~disco.types.invite.Invite`
            Returns a list of all invites for the channel.
        """
        return self.client.api.channels_invites_list(self.id)

    def create_invite(self, *args, **kwargs):
        """
        Create an invite for the channel

        Attempts to create a new invite with the given arguments. For more
        information see :func:`~disco.types.invite.Invite.create_for_channel`.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.types.invite.Invite.create_for_channel`
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.invite.Invite.create_for_channel`

        Returns
        -------
        :class:`~disco.types.invite.Invite`
            The generated invite for the channel
        """

        from disco.types.invite import Invite
        return Invite.create_for_channel(self, *args, **kwargs)

    def get_pins(self):
        """
        Get pinned messages

        Messages that have been pinned to the channel if there are any

        Returns
        -------
        list of :class:`~disco.types.message.Message`
            Returns a list of all pinned messages for the channel.
        """
        return self.client.api.channels_pins_list(self.id)

    def create_pin(self, message):
        """
        Pins the given message to the channel.
        

        Parameters
        ----------
        message : :class:`~disco.types.message.Message` or snowflake
            The message or message ID to pin.
        """
        self.client.api.channels_pins_create(self.id, to_snowflake(message))

    def delete_pin(self, message):
        """
        Unpins the given message from the channel.

        Parameters
        ----------
        message : :class:`~disco.types.message.Message` or snowflake
            The message or message ID to pin.
        """
        self.client.api.channels_pins_delete(self.id, to_snowflake(message))

    def get_webhooks(self):
        """
        Fetchs all webhooks operating on the channel
        
        Returns
        -------
        list of :class:`~disco.types.webhook.Webhook`
            Returns a list of all webhooks for the channel.
        """
        return self.client.api.channels_webhooks_list(self.id)

    def create_webhook(self, *args, **kwargs):
        """
        Creates a webhook

        Creates a webhook for the channel. See :func:`~disco.api.client.APIClient.channels_webhooks_create`
        for more information.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.api.client.APIClient.channels_webhooks_create`
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.channels_webhooks_create`

        Returns
        -------
        `Webhook`
            The created webhook.
        """
        return self.client.api.channels_webhooks_create(self.id, *args, **kwargs)

    def send_message(self, *args, **kwargs):
        """
        Send a message

        Send a message to the channel. See :func:`~disco.api.client.APIClient.channels_messages_create`
        for more information.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.api.client.APIClient.channels_messages_create`
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.channels_messages_create`

        Returns
        -------
        :class:`~disco.types.message.Message`
            The sent message.
        """
        return self.client.api.channels_messages_create(self.id, *args, **kwargs)

    def send_typing(self):
        """
        Signal typing status

        Sends a typing event to the channel. this will make it seem as though the bot is sending a message.
        This status is removed if a message is not sent before another typing event is sent, or a message is sent.
        See :func:`~disco.api.client.APIClient.channels_typing` for more information.
        """
        self.client.api.channels_typing(self.id)

    def create_overwrite(self, *args, **kwargs):
        """
        Create permission overwrite

        Creates a `PermissionOverwrite` for the channel.
        See `PermissionOverwrite.create_for_channel` for more information.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.types.channel.PermissionOverwrite.create_for_channel`
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.channel.PermissionOverwrite.create_for_channel`
        """
        return PermissionOverwrite.create_for_channel(self, *args, **kwargs)

    def delete_message(self, message):
        """
        Deletes a single message from the channel.

        Parameters
        ----------
        message : snowflake or :class:`~disco.types.message.Message`
            The message to delete.
        """
        self.client.api.channels_messages_delete(self.id, to_snowflake(message))

    @one_or_many
    def delete_messages(self, messages):
        """
        Deletes many messages

        Deletes a set of messages using the correct API route based on the number
        of messages passed.

        Parameters
        ----------
        messages : list of snowflake or list of :class:`~disco.types.message.Message`
            List of messages (or message ids) to delete. All messages must originate
            from the channel.
        """
        message_ids = list(map(to_snowflake, messages))

        if not message_ids:
            return

        if self.can(self.client.state.me, Permissions.MANAGE_MESSAGES) and len(messages) > 2:
            for chunk in chunks(message_ids, 100):
                self.client.api.channels_messages_delete_bulk(self.id, chunk)
        else:
            for msg in messages:
                self.delete_message(msg)

    def delete(self, **kwargs):
        """
        Delete guild channel

        Parameters
        ----------
        kwargs
            Keyword arguments to be passed into :func:`~disco.api.client.APIClient.channels_delete`

        Raises
        ------
        AssertionError
            Raised is the channel is a DM, or if the bot doesn't have MANAGE_CHANNELS permissions for this guild.
        """
        assert (self.is_dm or self.guild.can(self.client.state.me, Permissions.MANAGE_CHANNELS)), 'Invalid Permissions'
        self.client.api.channels_delete(self.id, **kwargs)

    def close(self):
        """
        Delete guild channel

        Copy of :func:`~disco.types.channel.Channel.delete`, but doesn't check if the bot has correct permissions
        """
        assert self.is_dm, 'Cannot close non-DM channel'
        self.delete()

    def set_topic(self, topic, reason=None):
        """
        Sets the channels topic.

        Parameters
        ----------
        topic : str
            The channel's topic or description
        reason : str, optional
            The reason for setting the topic

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel
        """
        return self.client.api.channels_modify(self.id, topic=topic, reason=reason)

    def set_name(self, name, reason=None):
        """
        Sets the channels name.

        Parameters
        ----------
        name : str
            The new channel name
        reason : str
            Reason for channel name update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel
        """
        return self.client.api.channels_modify(self.id, name=name, reason=reason)

    def set_position(self, position, reason=None):
        """
        Sets the channels position.

        Change the order which channels are listed.

        Parameters
        ----------
        position : int
            The new channel position (Check the guild to see how many channels it has)
        reason : str
            Reason for channel position update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel
        """
        return self.client.api.channels_modify(self.id, position=position, reason=reason)

    def set_nsfw(self, value, reason=None):
        """
        Sets whether the channel is NSFW.

        Parameters
        ----------
        value : bool
            Whether the channel should be NSFW or not
        reason : str
            Reason for channel nsfw update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel

        Raises
        ------
        AssertionError
            Raised if the channel type isn't a guild text channel
        """
        assert (self.type == ChannelType.GUILD_TEXT)
        return self.client.api.channels_modify(self.id, nsfw=value, reason=reason)

    def set_bitrate(self, bitrate, reason=None):
        """
        Sets the channels bitrate.

        Parameters
        ----------
        bitrate : int
            The voice channel's new bitrate
        reason : str
            Reason for channel bitrate update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel

        Raises
        ------
        AssertionError
            Raised if the channel isn't a voice channel
        """
        assert (self.is_voice)
        return self.client.api.channels_modify(self.id, bitrate=bitrate, reason=reason)

    def set_user_limit(self, user_limit, reason=None):
        """
        Sets the channels user limit.

        Voice channels can be capped at how many people can be in it, this method sets that limit.

        Parameters
        ----------
        user_limit : int
            The max amount of people in a voice channel
        reason : str
            Reason for channel user limit update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel

        Raises
        ------
        AssertionError
            Raised if channel isn't a voice channel
        """
        assert (self.is_voice)
        return self.client.api.channels_modify(self.id, user_limit=user_limit, reason=reason)

    def set_parent(self, parent, reason=None):
        """
        Sets the channels parent.

        Channels can be organized under categories, this method moves the channel under a category

        Parameters
        ----------
        parent : :class:`~disco.types.channel.Channel` or snowflake
            The category to move the channel under
        reason : str
            Reason for channel parent update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel

        Raises
        ------
        AssertionError
            Raised if the channel doesn't belong to a guild
        """
        assert (self.is_guild)
        return self.client.api.channels_modify(
            self.id,
            parent_id=to_snowflake(parent) if parent else parent,
            reason=reason)

    def set_slowmode(self, interval, reason=None):
        """
        Sets the channels slowmode

        Slowmode is used to restrict how many messages a user can send at once

        Parameters
        ----------
        interval : int
            The amount of seconds users have to wait after sending a message (between 0-21600 inclusive)
        reason : str
            Reason for channel slowmode update

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Updated version of the channel

        Raises
        ------
        AssertionError
            Raised if the channel is not a guild text channel
        """
        assert (self.type == ChannelType.GUILD_TEXT)
        return self.client.api.channels_modify(
            self.id,
            rate_limit_per_user=interval,
            reason=reason)

    def create_text_channel(self, *args, **kwargs):
        """
        Create text channel under this category

        Creates a text channel under this channel to keep channels organized.
        This can only be used if the channel is a category.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.types.guild.Guild.create_text_channel`
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.Guild.create_text_channel`

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Created text channel

        Raises
        ------
        ValueError
            Raised if the channel is not a category channel
        """
        if self.type != ChannelType.GUILD_CATEGORY:
            raise ValueError('Cannot create a sub-channel on a non-category channel')

        kwargs['parent_id'] = self.id
        return self.guild.create_text_channel(
            *args,
            **kwargs
        )

    def create_voice_channel(self, *args, **kwargs):
        """
        Create voice channel under this category

        Creates a voice channel under this channel to keep channels organized.
        This can only be used if the channel is a category.

        Parameters
        ----------
        args
            Arguments to be passed into :func:`~disco.types.guild.Guild.create_voice_channel`
        kwargs
            Keyword arguments to be passed into :func:`~disco.types.Guild.create_voice_channel`

        Returns
        -------
        :class:`~disco.types.channel.Channel`
            Created text channel

        Raises
        ------
        ValueError
            Raised if the channel is not a category channel
        """
        if self.type != ChannelType.GUILD_CATEGORY:
            raise ValueError('Cannot create a sub-channel on a non-category channel')

        kwargs['parent_id'] = self.id
        return self.guild.create_voice_channel(
            *args,
            **kwargs
        )


class MessageIterator(object):
    """
    Message iterator

    The discord API allows you to fetch 100 messages at once.
    After that 100 you need to create a new request based on the last messages's snowflake.
    This class makes interacting with the api much easier, and provides a constant stream of messages.
    This is used internally for :func:`~disco.types.channel.Channel.messages_iter`,
    and the :attr:`~disco.types.channel.Channel.messages` attribute.

    Attributes
    ----------
    client : :class:`~disco.client.Client`
        The disco client instance to use when making requests.
    channel : :class:`~disco.types.channel.Channel`
        The channel to iterate within.
    direction : :attr:`~disco.types.channel.MessageIterator.Direction`
        The direction in which the iterator will move.
    bulk : bool
        If true, the iterator will yield messages in list batches, otherwise each
        message will be yield individually.
    before : snowflake
        The message to begin scanning at.
    after : snowflake
        The message to begin scanning at.
    chunk_size : int
        The number of messages to request per API call.
    """
    class Direction(object):
        """
        What direction to go when traversing a channel

        Attributes
        ----------
        UP : int
            Search through messages earliest to oldest
        DOWN : int
            Search through messages oldest to earliest
        """
        UP = 1
        DOWN = 2

    def __init__(self, client, channel, direction=Direction.UP, bulk=False, before=None, after=None, chunk_size=100):
        self.client = client
        self.channel = channel
        self.direction = direction
        self.bulk = bulk
        self.before = before
        self.after = after
        self.chunk_size = chunk_size

        self.last = None
        self._buffer = []

        if before is None and after is None and self.direction == self.Direction.DOWN:
            raise Exception('Must specify either before or after for downward seeking')

    def fill(self):
        """
        Fetch messages

        Fills the internal buffer up with :class:`~disco.types.message.Message` objects from the API.

        Returns
        -------
        bool
            If True, the buffer was filled with more messages
        """
        self._buffer = self.client.api.channels_messages_list(
            self.channel.id,
            before=self.before,
            after=self.after,
            limit=self.chunk_size)

        if not len(self._buffer):
            return False

        self.after = None
        self.before = None

        if self.direction == self.Direction.UP:
            self.before = self._buffer[-1].id

        else:
            self._buffer.reverse()
            self.after = self._buffer[-1].id

        return True

    def next(self):
        """
        Get the next message

        Returns
        -------
        :class:`~disco.types.message.Message`
            The next message in the channel

        Raises
        ------
        StopIteration
            Raised when there are no more messages left
        """
        return self.__next__()

    def __iter__(self):
        return self

    def __next__(self):
        if not len(self._buffer):
            filled = self.fill()
            if not filled:
                raise StopIteration

        if self.bulk:
            res = self._buffer
            self._buffer = []
            return res
        else:
            return self._buffer.pop()
