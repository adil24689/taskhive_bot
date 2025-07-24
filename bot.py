print("Bot is starting...")

import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_IDS, PAYMENT_NUMBER
from db import *

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ✅ /start command – registration + referral
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    args = message.get_args()
    referred_by = int(args) if args.isdigit() and int(args) != message.from_user.id else None
    add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=message.from_user.full_name,
        referred_by=referred_by
    )
    await message.answer("👋 Welcome! You have received your joining bonus.")

# ✅ /myid – Show Telegram ID
@dp.message_handler(commands=['myid'])
async def myid_cmd(message: types.Message):
    await message.answer(f"🆔 Your Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


# ✅ /myprofile – Show user profile
@dp.message_handler(commands=['myprofile'])
async def profile_cmd(message: types.Message):
    user = get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👤 Name: {user[2]}\n"
            f"💰 Balance: {user[3]} Points\n"
            f"💼 Earnings: {user[4]} Points"
        )
    else:
        await message.answer("❌ User not found. Please send /start to register.")



# ✅ /tasks – List available tasks
@dp.message_handler(commands=['tasks'])
async def list_tasks(message: types.Message):
    tasks = get_active_tasks()
    if not tasks:
        await message.answer("📭 No active tasks right now. Please check back later.")
        return

    for task in tasks:
        task_id, user_id, task_type, title, desc, proof_type, total, completed, reward, hidden = task
        await message.answer(f"""📝 *{title}*
📌 Type: {task_type}
ℹ️ {desc}
🧾 Proof: {proof_type}
👥 {completed}/{total} Completed
💸 Reward: {reward} Points
🆔 Task ID: `{task_id}`

To submit, send: /submit {task_id}""", parse_mode="Markdown")



# ✅ FSM: Submit Task Proof

class SubmitProof(StatesGroup):
    waiting_for_task_id = State()
    waiting_for_proof = State()

@dp.message_handler(commands=['submit'])
async def submit_start(message: types.Message):
    args = message.get_args()
    if not args or not args.isdigit():
        await message.answer("❗ Please use the format: /submit TASK_ID")
        return

    task_id = int(args)
    task = None
    for t in get_active_tasks():
        if t[0] == task_id:
            task = t
            break

    if not task:
        await message.answer("❌ Invalid or inactive task ID.")
        return

    proof_type = task[5].lower()
    state = dp.current_state(user=message.from_user.id)
    await state.set_state(SubmitProof.waiting_for_proof.state)
    await state.update_data(task_id=task_id, proof_type=proof_type)

    if proof_type == "text":
        await message.answer("📝 Please send the text proof.")
    elif proof_type == "photo":
        await message.answer("📸 Please send the photo proof.")
    elif proof_type == "video":
        await message.answer("🎥 Please send the video file or YouTube link.")
    else:
        await message.answer("❌ Unknown proof type.")

@dp.message_handler(state=SubmitProof.waiting_for_proof, content_types=types.ContentTypes.ANY)
async def receive_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    proof_type = data['proof_type']
    task_id = data['task_id']

    proof = None
    if proof_type == "text" and message.text:
        proof = message.text
    elif proof_type == "photo" and message.photo:
        proof = message.photo[-1].file_id
    elif proof_type == "video":
        if message.video:
            proof = message.video.file_id
        elif message.text and "youtu" in message.text:
            proof = message.text

    if proof:
        submit_task(task_id, message.from_user.id, proof)
        await message.answer("✅ Your proof has been submitted for review.")
    else:
        await message.answer("❌ Invalid proof type. Please send the correct format.")
        return

    await state.finish()


# ✅ FSM: Post New Task

class PostTask(StatesGroup):
    waiting_for_type = State()
    waiting_for_title = State()
    waiting_for_desc = State()
    waiting_for_proof = State()
    waiting_for_total = State()
    waiting_for_reward = State()

TASK_TYPES = [
    "Facebook Page Follow + Invite Friends",
    "Facebook Group Member Invite",
    "YouTube Subscribe"
]

@dp.message_handler(commands=['posttask'])
async def posttask_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(*TASK_TYPES)
    await message.answer("📌 Select task type:", reply_markup=kb)
    await PostTask.waiting_for_type.set()

@dp.message_handler(state=PostTask.waiting_for_type)
async def posttask_type(message: types.Message, state: FSMContext):
    if message.text not in TASK_TYPES:
        await message.answer("❌ Please select a valid task type from the buttons.")
        return
    await state.update_data(task_type=message.text)
    await message.answer("📝 Send task title:", reply_markup=types.ReplyKeyboardRemove())
    await PostTask.next()

@dp.message_handler(state=PostTask.waiting_for_title)
async def posttask_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("ℹ️ Send task description:")
    await PostTask.next()

@dp.message_handler(state=PostTask.waiting_for_desc)
async def posttask_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("Text", "Photo", "Video")
    await message.answer("📸 Select proof type:", reply_markup=kb)
    await PostTask.next()

@dp.message_handler(state=PostTask.waiting_for_proof)
async def posttask_proof(message: types.Message, state: FSMContext):
    if message.text not in ["Text", "Photo", "Video"]:
        await message.answer("❌ Choose proof type from buttons.")
        return
    await state.update_data(proof_type=message.text.lower())
    await message.answer("👥 Enter total number of workers:", reply_markup=types.ReplyKeyboardRemove())
    await PostTask.next()

@dp.message_handler(state=PostTask.waiting_for_total)
async def posttask_total(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗ Enter a valid number.")
        return
    await state.update_data(total_workers=int(message.text))
    await message.answer("💸 Enter reward per worker (points):")
    await PostTask.next()

@dp.message_handler(state=PostTask.waiting_for_reward)
async def posttask_reward(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗ Enter a valid number.")
        return

    reward = int(message.text)
    data = await state.get_data()
    total_cost = reward * data['total_workers']
    user = get_user(message.from_user.id)

    if user[3] < total_cost:
        await message.answer(f"❌ You need {total_cost} points but you have only {user[3]}.")
        await state.finish()
        return

    deduct_points(message.from_user.id, total_cost)
    create_task(
        user_id=message.from_user.id,
        task_type=data['task_type'],
        title=data['title'],
        desc=data['description'],
        proof=data['proof_type'],
        total=data['total_workers'],
        reward=reward
    )
    await message.answer("✅ Task posted successfully!")
    await state.finish()


# ✅ FSM: Recharge Points

class RechargeFSM(StatesGroup):
    waiting_for_amount = State()
    waiting_for_method = State()
    waiting_for_trx = State()

@dp.message_handler(commands=['recharge'])
async def recharge_start(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("100", "200", "300", "400", "500")
    await message.answer("💰 Choose amount to recharge:", reply_markup=kb)
    await RechargeFSM.waiting_for_amount.set()

@dp.message_handler(state=RechargeFSM.waiting_for_amount)
async def recharge_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Enter a valid amount.")
        return
    await state.update_data(amount=int(message.text))
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("bKash", "Nagad")
    await message.answer("📲 Choose payment method:", reply_markup=kb)
    await RechargeFSM.next()

@dp.message_handler(state=RechargeFSM.waiting_for_method)
async def recharge_method(message: types.Message, state: FSMContext):
    if message.text not in ["bKash", "Nagad"]:
        await message.answer("❌ Choose from bKash or Nagad.")
        return
    await state.update_data(method=message.text)
    await message.answer(
        f"""📨 Send your {message.text} number & TrxID (screenshot optional).
Example: 01XXXXXXXXX, TX1234567""",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await RechargeFSM.next()


@dp.message_handler(state=RechargeFSM.waiting_for_trx)
async def recharge_trx(message: types.Message, state: FSMContext):
    data = await state.get_data()
    log_recharge(message.from_user.id, data['amount'], data['method'], message.text)
    await message.answer("✅ Recharge request submitted! Admin will verify and add points soon.")
    await state.finish()


# ✅ FSM: Withdraw Points

class WithdrawFSM(StatesGroup):
    waiting_for_amount = State()
    waiting_for_method = State()
    waiting_for_number = State()

@dp.message_handler(commands=['withdraw'])
async def withdraw_start(message: types.Message):
    await message.answer("💸 Enter amount to withdraw (e.g., 100, 200):")
    await WithdrawFSM.waiting_for_amount.set()

@dp.message_handler(state=WithdrawFSM.waiting_for_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗ Enter a valid number.")
        return
    amount = int(message.text)
    user = get_user(message.from_user.id)
    if user[3] < amount * COIN_RATE:
        await message.answer(f"❌ You need {amount * COIN_RATE} points but you have only {user[3]}.")
        await state.finish()
        return
    await state.update_data(amount=amount)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add("bKash", "Nagad")
    await message.answer("📲 Choose withdrawal method:", reply_markup=kb)
    await WithdrawFSM.next()

@dp.message_handler(state=WithdrawFSM.waiting_for_method)
async def withdraw_method(message: types.Message, state: FSMContext):
    if message.text not in ["bKash", "Nagad"]:
        await message.answer("❌ Choose from bKash or Nagad.")
        return
    await state.update_data(method=message.text)
    await message.answer("📞 Enter your number:", reply_markup=types.ReplyKeyboardRemove())
    await WithdrawFSM.next()

@dp.message_handler(state=WithdrawFSM.waiting_for_number)
async def withdraw_number(message: types.Message, state: FSMContext):
    data = await state.get_data()
    deduct_points(message.from_user.id, data['amount'] * COIN_RATE)
    request_withdraw(message.from_user.id, data['amount'], data['method'], message.text)
    await message.answer("✅ Withdrawal request submitted. Admin will send money shortly.")
    await state.finish()


# ✅ /admin_panel – Admin Dashboard

@dp.message_handler(commands=['admin_panel'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ You are not authorized.")
        return

    users = len(get_all_users()) if callable(globals().get("get_all_users")) else "N/A"
    tasks = len(get_active_tasks())
    submissions = len(get_submissions())
    recharges = len(get_pending_recharges())
    withdrawals = len(get_pending_withdrawals())

    await message.answer(f"""🛠️ Admin Panel

👤 Total Users: {users}
📋 Total Tasks: {tasks}
📝 Pending Submissions: {submissions}
💸 Pending Recharges: {recharges}
🏦 Pending Withdrawals: {withdrawals}""")



@dp.message_handler(commands=['admin_submissions'])
async def show_pending_submissions(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ Unauthorized")

    submissions = get_submissions()
    if not submissions:
        return await message.answer("📭 No pending submissions.")
    
    for sub in submissions:
        submission_id, task_id, worker_id, proof, status = sub
        await message.answer(
            f"📝 Submission ID: {submission_id}\n"
            f"🆔 Task ID: {task_id}\n"
            f"👤 User ID: {worker_id}\n"
            f"📎 Proof: {proof}\n"
            f"⏳ Status: {status}\n\n"
            f"✅ Approve: /approve_{submission_id}\n❌ Reject: /reject_{submission_id}"
        )




























@dp.message_handler(commands=['admin_recharges'])
async def show_recharges(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ Unauthorized")

    recharges = get_pending_recharges()
    if not recharges:
        return await message.answer("📭 No pending recharges.")
    
    for r in recharges:
        recharge_id, user_id, amount, method, trx_id, verified = r
        await message.answer(
            f"💳 Recharge ID: {recharge_id}\n"
            f"👤 User ID: {user_id}\n"
            f"💰 Amount: {amount} BDT\n"
            f"📲 Method: {method}\n"
            f"📎 TrxID: {trx_id}\n\n"
            f"✅ Approve: /approve_recharge_{recharge_id}"
        )

@dp.message_handler(lambda m: m.text.startswith("/approve_recharge_"))
async def approve_recharge_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    recharge_id = int(message.text.split("_")[-1])
    verify_recharge(recharge_id)
    await message.answer("✅ Recharge approved.")




@dp.message_handler(commands=['admin_withdrawals'])
async def show_withdrawals(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("❌ Unauthorized")

    withdrawals = get_pending_withdrawals()
    if not withdrawals:
        return await message.answer("📭 No pending withdrawals.")
    
    for w in withdrawals:
        withdrawal_id, user_id, amount, method, number, verified = w
        await message.answer(
            f"🏧 Withdrawal ID: {withdrawal_id}\n"
            f"👤 User ID: {user_id}\n"
            f"💵 Amount: {amount} BDT\n"
            f"📲 Method: {method}\n"
            f"📞 Number: {number}\n\n"
            f"✅ Approve: /approve_withdraw_{withdrawal_id}"
        )


@dp.message_handler(lambda m: m.text.startswith("/approve_withdraw_"))
async def approve_withdrawal_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        withdrawal_id = int(message.text.split("_")[-1])
        verify_withdraw(withdrawal_id)
        await message.answer("✅ Withdrawal approved.")
    except:
        await message.answer("❌ Invalid command.")



@dp.message_handler(lambda m: m.text.startswith("/approve_") and m.text.replace("/approve_", "").isdigit())
async def approve_submission_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    submission_id = int(message.text.replace("/approve_", ""))
    review_submission(submission_id, approve=True)
    await message.answer("✅ Submission approved.")

@dp.message_handler(lambda m: m.text.startswith("/reject_") and m.text.replace("/reject_", "").isdigit())
async def reject_submission_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    submission_id = int(message.text.replace("/reject_", ""))
    review_submission(submission_id, approve=False)
    await message.answer("❌ Submission rejected.")



if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)


    # Optionally, list each for admin review in future steps


# ✅ All core features implemented