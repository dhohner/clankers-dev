#import <Foundation/Foundation.h>

// Match terminal-notifier 3.1.0's NSUserDefaults lookup and single-backslash unescape.
int main(void) {
  @autoreleasepool {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    NSMutableArray *values = [NSMutableArray array];
    for (NSString *key in @[@"title", @"message"]) {
      id value = [defaults objectForKey:key];
      if (![value isKindOfClass:[NSString class]]) return 2;
      if ([value hasPrefix:@"\\"]) value = [value substringFromIndex:1];
      [values addObject:value];
    }
    id activation = [defaults objectForKey:@"activate"];
    if (activation) {
      if (![activation isKindOfClass:[NSString class]]) return 3;
      [values addObject:activation];
    }
    NSData *json = [NSJSONSerialization dataWithJSONObject:values options:0 error:nil];
    fwrite(json.bytes, 1, json.length, stdout);
  }
  return 0;
}
