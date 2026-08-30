
import os
import asyncio
import discord

from discord.ext import commands
from discord import app_commands

from dotenv import load_dotenv

from flask import Flask
from threading import Thread


# =========================================================
# 환경 변수
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

GUILD_ID = int(
    os.getenv("GUILD_ID", "0")
)

VERIFY_CHANNEL_ID = int(
    os.getenv("VERIFY_CHANNEL_ID", "0")
)

STAFF_ROLE_ID = int(
    os.getenv("STAFF_ROLE_ID", "0")
)

VERIFIED_ROLE_ID = int(
    os.getenv("VERIFIED_ROLE_ID", "0")
)

UNVERIFIED_ROLE_ID = int(
    os.getenv("UNVERIFIED_ROLE_ID", "0")
)

TICKET_CATEGORY_ID = int(
    os.getenv("TICKET_CATEGORY_ID", "0")
)


# =========================================================
# Render Web Service용 웹 서버
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():

    return "Discord Bot is running!"


@app.route("/health")
def health():

    return "OK"


def run_web():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


def keep_web_alive():

    thread = Thread(
        target=run_web,
        daemon=True
    )

    thread.start()


# =========================================================
# Discord 기본 설정
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True


bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# 봇 시작
# =========================================================

@bot.event
async def on_ready():

    print("=" * 50)

    print(
        f"로그인 완료: {bot.user}"
    )

    print(
        f"봇 ID: {bot.user.id}"
    )

    print("=" * 50)

    try:

        guild = discord.Object(
            id=GUILD_ID
        )

        synced = await bot.tree.sync(
            guild=guild
        )

        print(
            f"슬래시 명령어 동기화 완료: "
            f"{len(synced)}개"
        )

    except Exception as e:

        print(
            "슬래시 명령어 동기화 실패:"
        )

        print(e)


# =========================================================
# 처리단 확인
# =========================================================

def is_staff(
    member: discord.Member
):

    return any(
        role.id == STAFF_ROLE_ID
        for role in member.roles
    )


# =========================================================
# 티켓 번호
# =========================================================

async def get_ticket_number(
    guild: discord.Guild
):

    category = guild.get_channel(
        TICKET_CATEGORY_ID
    )

    if not isinstance(
        category,
        discord.CategoryChannel
    ):

        return 1

    numbers = []

    for channel in category.channels:

        if not channel.name.startswith(
            "ticket-"
        ):

            continue

        try:

            number = int(
                channel.name.split("-")[1]
            )

            numbers.append(number)

        except ValueError:

            pass

    if not numbers:

        return 1

    return max(numbers) + 1


# =========================================================
# 인증 완료 버튼
# =========================================================

class VerifyCompleteButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="인증완료",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id="verify_complete"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        # ---------------------------------------------
        # 처리단 확인
        # ---------------------------------------------

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ 처리단만 사용할 수 있습니다.",
                ephemeral=True
            )

            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "❌ 올바른 티켓 채널이 아닙니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 티켓 소유자
        # ---------------------------------------------

        owner_id = channel.topic

        if not owner_id:

            await interaction.response.send_message(
                "❌ 티켓 소유자를 찾을 수 없습니다.",
                ephemeral=True
            )

            return

        try:

            owner_id = int(
                owner_id
            )

        except ValueError:

            await interaction.response.send_message(
                "❌ 티켓 정보가 잘못되었습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 멤버 찾기
        # ---------------------------------------------

        member = interaction.guild.get_member(
            owner_id
        )

        if member is None:

            try:

                member = await interaction.guild.fetch_member(
                    owner_id
                )

            except discord.NotFound:

                await interaction.response.send_message(
                    "❌ 서버에서 해당 사용자를 찾을 수 없습니다.",
                    ephemeral=True
                )

                return

            except discord.HTTPException:

                await interaction.response.send_message(
                    "❌ 사용자 정보를 가져오는 중 오류가 발생했습니다.",
                    ephemeral=True
                )

                return

        # ---------------------------------------------
        # 역할
        # ---------------------------------------------

        verified_role = interaction.guild.get_role(
            VERIFIED_ROLE_ID
        )

        unverified_role = interaction.guild.get_role(
            UNVERIFIED_ROLE_ID
        )

        if verified_role is None:

            await interaction.response.send_message(
                "❌ 인증완료 역할을 찾을 수 없습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 인증완료 역할 추가
        # ---------------------------------------------

        try:

            await member.add_roles(
                verified_role,
                reason=(
                    f"인증 완료 - "
                    f"처리자: {interaction.user}"
                )
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ 봇이 인증완료 역할을 지급할 권한이 없습니다.\n"
                "봇의 역할을 인증완료 역할보다 위로 올려주세요.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            print(
                "인증 역할 지급 오류:",
                e
            )

            await interaction.response.send_message(
                "❌ 역할 지급 중 Discord 오류가 발생했습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 미인증 역할 제거
        # ---------------------------------------------

        if unverified_role:

            try:

                await member.remove_roles(
                    unverified_role,
                    reason=(
                        f"인증 완료 - "
                        f"처리자: {interaction.user}"
                    )
                )

            except discord.Forbidden:

                print(
                    "미인증 역할 제거 권한 없음"
                )

            except discord.HTTPException as e:

                print(
                    "미인증 역할 제거 오류:",
                    e
                )

        # ---------------------------------------------
        # 처리단에게 표시
        # ---------------------------------------------

        await interaction.response.send_message(
            f"✅ **{member.display_name}**님의 "
            f"인증이 완료되었습니다.",
            ephemeral=True
        )

        # ---------------------------------------------
        # 티켓 메시지
        # ---------------------------------------------

        try:

            await channel.send(
                f"✅ {member.mention}님의 인증이 완료되었습니다.\n"
                f"처리자: {interaction.user.mention}"
            )

        except discord.HTTPException:

            pass

        # ---------------------------------------------
        # 티켓 삭제
        # ---------------------------------------------

        await asyncio.sleep(3)

        try:

            await channel.delete(
                reason=(
                    f"인증 완료 - "
                    f"처리자: {interaction.user}"
                )
            )

        except discord.NotFound:

            pass

        except discord.Forbidden:

            print(
                "티켓 삭제 권한 없음"
            )


# =========================================================
# 반려 버튼
# =========================================================

class RejectButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="반려",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id="verify_reject"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not isinstance(
            interaction.user,
            discord.Member
        ):

            return

        # ---------------------------------------------
        # 처리단 확인
        # ---------------------------------------------

        if not is_staff(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ 처리단만 사용할 수 있습니다.",
                ephemeral=True
            )

            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "❌ 올바른 티켓 채널이 아닙니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 반려
        # ---------------------------------------------

        await interaction.response.send_message(
            "❌ 인증 신청이 반려되었습니다. "
            "티켓을 삭제합니다.",
            ephemeral=True
        )

        await asyncio.sleep(2)

        try:

            await channel.delete(
                reason=(
                    f"인증 반려 - "
                    f"처리자: {interaction.user}"
                )
            )

        except discord.NotFound:

            pass

        except discord.Forbidden:

            print(
                "티켓 삭제 권한 없음"
            )


# =========================================================
# 처리 패널
# =========================================================

class StaffVerifyView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            VerifyCompleteButton()
        )

        self.add_item(
            RejectButton()
        )


# =========================================================
# 인증 신청 버튼
# =========================================================

class CreateTicketButton(
    discord.ui.Button
):

    def __init__(self):

        super().__init__(
            label="인증 신청",
            emoji="🎫",
            style=discord.ButtonStyle.primary,
            custom_id="create_verify_ticket"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # 가장 먼저 응답
        #
        # Discord Interaction은 제한 시간이 있으므로
        # 티켓 생성 전에 defer를 한다.
        # =================================================

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild

        if guild is None:

            await interaction.followup.send(
                "❌ 서버에서만 사용할 수 있습니다.",
                ephemeral=True
            )

            return

        member = interaction.user

        # ---------------------------------------------
        # 이미 인증됐는지 확인
        # ---------------------------------------------

        verified_role = guild.get_role(
            VERIFIED_ROLE_ID
        )

        if (
            verified_role
            and verified_role in member.roles
        ):

            await interaction.followup.send(
                "✅ 이미 인증된 사용자입니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 카테고리
        # ---------------------------------------------

        category = guild.get_channel(
            TICKET_CATEGORY_ID
        )

        if not isinstance(
            category,
            discord.CategoryChannel
        ):

            await interaction.followup.send(
                "❌ 티켓 카테고리를 찾을 수 없습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 기존 티켓 확인
        # ---------------------------------------------

        for channel in category.channels:

            if not isinstance(
                channel,
                discord.TextChannel
            ):

                continue

            if channel.topic == str(
                member.id
            ):

                await interaction.followup.send(
                    f"⚠️ 이미 열린 인증 티켓이 있습니다: "
                    f"{channel.mention}",
                    ephemeral=True
                )

                return

        # ---------------------------------------------
        # 티켓 번호
        # ---------------------------------------------

        ticket_number = await get_ticket_number(
            guild
        )

        ticket_name = (
            f"ticket-{ticket_number:02d}"
        )

        # ---------------------------------------------
        # 처리단 역할
        # ---------------------------------------------

        staff_role = guild.get_role(
            STAFF_ROLE_ID
        )

        if staff_role is None:

            await interaction.followup.send(
                "❌ 처리단 역할을 찾을 수 없습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 봇 멤버
        # ---------------------------------------------

        bot_member = guild.me

        if bot_member is None:

            await interaction.followup.send(
                "❌ 봇 정보를 가져올 수 없습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 권한
        # ---------------------------------------------

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            member:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            staff_role:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            bot_member:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_roles=True,
                    read_message_history=True
                )
        }

        # ---------------------------------------------
        # 티켓 생성
        # ---------------------------------------------

        try:

            ticket = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=str(member.id),
                reason=(
                    f"인증 티켓 생성 - {member}"
                )
            )

        except discord.Forbidden:

            await interaction.followup.send(
                "❌ 티켓을 생성할 권한이 없습니다.\n"
                "봇에게 **채널 관리** 권한이 있는지 확인해주세요.",
                ephemeral=True
            )

            return

        except discord.HTTPException as e:

            print(
                "티켓 생성 HTTP 오류:",
                e
            )

            await interaction.followup.send(
                "❌ 티켓 생성 중 Discord API 오류가 발생했습니다.",
                ephemeral=True
            )

            return

        except Exception as e:

            print(
                "티켓 생성 오류:",
                e
            )

            await interaction.followup.send(
                "❌ 티켓 생성 중 알 수 없는 오류가 발생했습니다.",
                ephemeral=True
            )

            return

        # ---------------------------------------------
        # 사용자에게 알림
        # ---------------------------------------------

        await interaction.followup.send(
            f"🎫 인증 티켓이 생성되었습니다.\n"
            f"{ticket.mention}",
            ephemeral=True
        )

        # ---------------------------------------------
        # 티켓 메시지
        # ---------------------------------------------

        try:

            await ticket.send(

                content=(
                    f"{member.mention} "
                    f"{staff_role.mention}"
                ),

                embed=discord.Embed(
                    title="🎫 인증 신청",
                    description=(
                        "인증 신청이 접수되었습니다.\n\n"
                        "처리단에서 신청 내용을 확인한 후 "
                        "**인증완료** 또는 **반려**를 눌러주세요."
                    ),
                    color=discord.Color.blue()
                ),

                view=StaffVerifyView()
            )

        except discord.HTTPException as e:

            print(
                "티켓 메시지 전송 오류:",
                e
            )


# =========================================================
# 인증 패널
# =========================================================

class VerifyPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            CreateTicketButton()
        )


# =========================================================
# /인증패널
# =========================================================

@bot.tree.command(
    name="인증패널",
    description="인증 신청 패널을 생성합니다."
)
@app_commands.guilds(
    discord.Object(
        id=GUILD_ID
    )
)
async def verification_panel(
    interaction: discord.Interaction
):

    if not isinstance(
        interaction.user,
        discord.Member
    ):

        return

    # ---------------------------------------------
    # 관리자 / 처리단 확인
    # ---------------------------------------------

    if (
        not is_staff(interaction.user)
        and not interaction.user.guild_permissions.administrator
    ):

        await interaction.response.send_message(
            "❌ 관리자 또는 처리단만 사용할 수 있습니다.",
            ephemeral=True
        )

        return

    # ---------------------------------------------
    # 인증 채널
    # ---------------------------------------------

    channel = interaction.guild.get_channel(
        VERIFY_CHANNEL_ID
    )

    if not isinstance(
        channel,
        discord.TextChannel
    ):

        await interaction.response.send_message(
            "❌ 인증 채널을 찾을 수 없습니다.",
            ephemeral=True
        )

        return

    # ---------------------------------------------
    # Embed
    # ---------------------------------------------

    embed = discord.Embed(
        title="🔐 서버 인증",
        description=(
            "서버를 이용하려면 인증이 필요합니다.\n\n"
            "아래의 **인증 신청** 버튼을 눌러주세요.\n"
            "인증 신청 후 처리단이 확인합니다."
        ),
        color=discord.Color.green()
    )

    embed.set_footer(
        text="인증 시스템"
    )

    # ---------------------------------------------
    # 패널 전송
    # ---------------------------------------------

    try:

        await channel.send(
            embed=embed,
            view=VerifyPanelView()
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ 인증 채널에 메시지를 보낼 권한이 없습니다.",
            ephemeral=True
        )

        return

    except discord.HTTPException as e:

        print(
            "인증 패널 전송 오류:",
            e
        )

        await interaction.response.send_message(
            "❌ 인증 패널 전송 중 Discord 오류가 발생했습니다.",
            ephemeral=True
        )

        return

    # ---------------------------------------------
    # 완료
    # ---------------------------------------------

    await interaction.response.send_message(
        f"✅ 인증 패널을 "
        f"{channel.mention}에 생성했습니다.",
        ephemeral=True
    )


# =========================================================
# View 재등록
# =========================================================

@bot.event
async def setup_hook():

    # 봇 재시작 후에도 기존 버튼 유지

    bot.add_view(
        VerifyPanelView()
    )

    bot.add_view(
        StaffVerifyView()
    )


# =========================================================
# 실행
# =========================================================

if not TOKEN:

    print(
        "❌ DISCORD_TOKEN이 없습니다."
    )

else:

    print(
        "🌐 Render 웹 서버 시작..."
    )

    keep_web_alive()

    print(
        "🤖 Discord 봇 시작..."
    )

    bot.run(TOKEN)
