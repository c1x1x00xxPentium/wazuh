/* Copyright (C) 2015-2021, Wazuh Inc.
 * All rights reserved.
 *
 * This program is free software; you can redistribute it
 * and/or modify it under the terms of the GNU General Public
 * License (version 2) as published by the FSF - Free Software
 * Foundation.
 */

#ifndef _OP_BUILDER_KVDB_H
#define _OP_BUILDER_KVDB_H

#include "builderTypes.hpp"

namespace builder::internals::builders
{

types::Lifter opBuilderKVDBExtract(const types::DocumentValue & def);
types::Lifter opBuilderKVDBMatch(const types::DocumentValue & def);
types::Lifter opBuilderKVDBNotMatch(const types::DocumentValue & def);

}

// namespace builder::internals::builders

#endif // _OP_BUILDER_MAP_H
