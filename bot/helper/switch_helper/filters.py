from swibots import filters

from bot import user_data, OWNER_ID


class CustomFilters:
    async def owner_filter(self, ctx):
        return ctx.event.action_by_id == OWNER_ID

    owner = filters.create(owner_filter)

    async def authorized_user(self, ctx):
        uid = ctx.event.action_by_id
        chat_id = ctx.event.community_id
        return bool(
            uid == OWNER_ID
            or (
                uid in user_data
                and (
                    user_data[uid].get("is_auth", False)
                    or user_data[uid].get("is_sudo", False)
                )
            )
            or (chat_id in user_data and user_data[chat_id].get("is_auth", False))
        )

    authorized = filters.create(authorized_user)

    async def sudo_user(self, ctx):
        uid = ctx.event.action_by_id
        return bool(
            uid == OWNER_ID or uid in user_data and user_data[uid].get("is_sudo")
        )

    sudo = filters.create(sudo_user)
