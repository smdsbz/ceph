// -*- mode:C++; tab-width:8; c-basic-offset:2; indent-tabs-mode:t -*-
// vim: ts=8 sw=2 smarttab
/*
 * Ceph - scalable distributed file system
 *
 * Copyright (C) 2019 Red Hat <contact@redhat.com>
 * Author: Adam C. Emerson <aemerson@redhat.com>
 *
 * This is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License version 2.1, as published by the Free Software
 * Foundation.  See file COPYING.
 *
 */

#include <string>

#include "common/error_code.h"
#include "common/errno.h"
#include "error_code.h"

class osd_error_category : public ceph::converting_category {
public:
  osd_error_category(){}
  const char* name() const noexcept override;
  std::string message(int ev) const override;
  boost::system::error_condition default_error_condition(int ev) const noexcept
    override;
  bool equivalent(int ev, const boost::system::error_condition& c) const
    noexcept override;
  using ceph::converting_category::equivalent;
  int from_code(int ev) const noexcept override;
};

const char* osd_error_category::name() const noexcept {
  return "osd";
}

std::string osd_error_category::message(int ev) const {
  if (ev == 0)
    return "No error";

  switch (static_cast<osd_errc>(ev)) {
  case osd_errc::old_snapc:
    return "ORDERSNAP flag set; writer has old snapc";
  case osd_errc::blacklisted:
    return "Blacklisted";
  }

  return cpp_strerror(ev);
}

boost::system::error_condition osd_error_category::default_error_condition(int ev) const noexcept {
  if (ev == static_cast<int>(osd_errc::old_snapc) ||
      ev == static_cast<int>(osd_errc::blacklisted))
    return { ev, *this };
  else
    return { ev, boost::system::generic_category() };
}

bool osd_error_category::equivalent(int ev, const boost::system::error_condition& c) const noexcept {
  switch (static_cast<osd_errc>(ev)) {
  case osd_errc::old_snapc:
      return c == boost::system::errc::invalid_argument;
  case osd_errc::blacklisted:
      return c == boost::system::errc::operation_not_permitted;
  }
  return default_error_condition(ev) == c;
}

int osd_error_category::from_code(int ev) const noexcept {
  return -ev;
}

const boost::system::error_category& osd_category() noexcept {
  static const osd_error_category c;
  return c;
}
