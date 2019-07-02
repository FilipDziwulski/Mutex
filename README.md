*Mutex*: In computer programming, a mutex (mutual exclusion object) is a program object that is created so that multiple program threads can take turns sharing the same resource, such as access to a file.

Mutex was created to make sharing company resources among multiple competing groups or people a bit easier.

*Slash Commands:*
*/lock* [resource, duration in hours, reason]
*/unlock* [resource]

The params are optional, comma separated, but need to be in order.
*ex.*  _/lock vehicle1, .3, To test whether it's autonomous yet_

If you don't enter a resource name, the name of the channel is used. If you don't enter a duration, or you write 0, the lock doesn't expire and you will need to remember to unlock it. A reason is also optional, but nice.

You can attempt to lock a resource at any time. If it's already locked, you will be shown who owns it, why, and till when. You will be tagged/notified when the owner releases it or when it expires.

If you own a resource, you can re-lock anytime with a new duration or reason to extend your ownership.