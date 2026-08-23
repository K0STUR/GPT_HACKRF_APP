#include "ui.hpp"
#include "ui_wifi_aim.hpp"
#include "ui_navigation.hpp"
#include "external_app.hpp"

namespace ui::external_app::wifi_aim {
void initialize_app(ui::NavigationView& nav) {
    nav.push<WifiAimView>();
}
}

extern "C" {
__attribute__((section(".external_app.app_wifi_aim.application_information"), used))
application_information_t _application_information_wifi_aim = {
    /*.memory_location = */ (uint8_t*)0x00000000,
    /*.externalAppEntry = */ ui::external_app::wifi_aim::initialize_app,
    /*.header_version = */ CURRENT_HEADER_VERSION,
    /*.app_version = */ VERSION_MD5,
    /*.app_name = */ "WiFi AIM",
    /*.bitmap_data = */ {0x00,0x00,0xE0,0x07,0x18,0x18,0x04,0x20,0xE2,0x47,0x12,0x48,0xCA,0x53,0x2A,0x54,0x2A,0x54,0xCA,0x53,0x12,0x48,0xE2,0x47,0x04,0x20,0x18,0x18,0xE0,0x07,0x00,0x00},
    /*.icon_color = */ ui::Color::cyan().v,
    /*.menu_location = */ app_location_t::RX,
    /*.desired_menu_position = */ -1,
    /*.m4_app_tag = */ {'W','A','I','M'},
    /*.m4_app_offset = */ 0x00000000,
};
}
