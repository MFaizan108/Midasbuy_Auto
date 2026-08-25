# Centralized selectors requiring live Midasbuy verification
HELP_AND_DRAW_BUTTONS=['text=Help & Draw','button:has-text("Help")','[data-testid="help-draw"]']
HELP_DRAW_EXACT_TEXT='Help & Draw'
LOGIN_INDICATORS=['text=Login','text=Sign in']
AUTHENTICATED_USER_CONTROL="[data-id='user_name']"
AUTHENTICATED_PANEL="[class*='MidasbuyUI-user_mess_box_'][class*='MidasbuyUI-show_']"
AUTHENTICATED_LOGOUT="text=Log Out"
AUTHENTICATED_LOGOUT_SELECTORS=["text=Log Out","text=Logout","text=Log out"]
AUTHENTICATED_INDICATORS=[AUTHENTICATED_LOGOUT]
SUCCESS_INDICATORS=['text=Success','text=Completed','text=You helped']
HELP_DRAW_RESULT_POPUP=".popupWrap_1cdkN"
HELP_DRAW_RESULT_WRAPPER=".popupGiftWrap_Bt7Jn"
HELP_DRAW_COUPON=".couponWrap_mJm4J"
HELP_DRAW_AMOUNT=".number_2R2xf"
HELP_DRAW_SUCCESS_TEXT="The Top-up Bonus Coupon has been automatically sent to your account"

# Startup popup selectors (confirmed via live site inspection)
STARTUP_POPUP_CONTAINER="[data-component-id='hot_game_entry']"
STARTUP_POPUP_CLOSE="[data-component-id='hot_game_entry'] .MidasbuyUI-close_btn_838ad3"
STARTUP_POPUP_OVERLAY=".MidasbuyUI-pop_bg_0f23b2"

# Additional popup selectors for Midasbuy variations
# "Add to homescreen" / install app popup
HOMESCREEN_POPUP_CONTAINER="[data-component-id='add_to_home_screen'], [class*='MidasbuyUI-add_to_home'], [class*='MidasbuyUI-install_app']"
HOMESCREEN_POPUP_CLOSE="[data-component-id='add_to_home_screen'] .MidasbuyUI-close_btn_838ad3, [class*='MidasbuyUI-add_to_home'] .MidasbuyUI-close_btn_838ad3, [class*='MidasbuyUI-install_app'] .MidasbuyUI-close_btn_838ad3"

# Generic Midasbuy close buttons (fallback for any Midasbuy modal/popup)
GENERIC_MIDASBUY_CLOSE=".MidasbuyUI-close_btn_838ad3, [class*='MidasbuyUI-close'], button[aria-label='Close'], button[aria-label='close']"
