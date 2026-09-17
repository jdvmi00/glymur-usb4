/* SPDX-License-Identifier: GPL-2.0-only */
/* Expected assertion failures must fail tests without invoking crash handlers. */
#ifndef GLYMUR_TEST_HARNESS_H
#define GLYMUR_TEST_HARNESS_H

#include <signal.h>
#include <stdio.h>
#include <stdlib.h>

static void harness_assertion_exit(int signal_number)
{
	(void)signal_number;
	_Exit(134);
}

__attribute__((constructor)) static void harness_install_abort_handler(void)
{
	if (signal(SIGABRT, harness_assertion_exit) == SIG_ERR) {
		perror("test harness: cannot install assertion handler");
		_Exit(125);
	}
}

#endif
